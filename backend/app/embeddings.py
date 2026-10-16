"""
embeddings.py — Text Embedding with Sentence Transformers

What are embeddings?
--------------------
An embedding is a numerical representation of text as a vector
(a list of floating-point numbers). The key property is:
texts that are semantically similar produce vectors that are close
together in the high-dimensional space.

Example:
    "What is the boiling point of water?" → [0.12, -0.34, 0.87, ...]
    "At what temperature does water boil?" → [0.11, -0.35, 0.85, ...]
    "The stock market fell today."         → [-0.54, 0.21, -0.12, ...]

The first two are semantically similar, so their vectors are close.
The third is unrelated, so its vector is far away.

This is fundamentally different from keyword search, which would
find no overlap between "boiling point" and "temperature does water boil"
because the exact words don't match.

Model: all-MiniLM-L6-v2
-----------------------
- Produces 384-dimensional vectors
- Small (~80 MB), fast, and good quality for English text
- Available free from HuggingFace
- Downloaded automatically on first use and cached locally

Singleton pattern:
------------------
The model is loaded once per process (not per request).
The module-level _model variable is None until first use,
then set and reused forever. This is called lazy initialization.
"""

# Must be set before sentence_transformers is imported
import os
os.environ.setdefault("USE_TF", "0")
os.environ.setdefault("TRANSFORMERS_NO_TF", "1")

import numpy as np
import logging
from sentence_transformers import SentenceTransformer
from app.config import settings

logger = logging.getLogger(__name__)

# Module-level model instance — None until first call to get_embedding_model()
# This is the "singleton" — one shared object for the whole process
_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    """
    Return the loaded embedding model.
    Loads it on first call, then reuses the cached instance.

    This function is called by:
    - embed_chunks() during document upload
    - embed_query() during question answering

    The first call takes a few seconds (loading 80MB model).
    All subsequent calls return instantly.
    """
    global _model

    if _model is None:
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        logger.info("This takes a moment on first run — model is downloading/loading...")

        _model = SentenceTransformer(settings.embedding_model)

        # Log the model's vector dimension for debugging
        # all-MiniLM-L6-v2 produces 384-dimensional vectors
        test_vec = _model.encode(["test"], convert_to_numpy=True)
        logger.info(
            f"Embedding model loaded. Vector dimension: {test_vec.shape[1]}"
        )

    return _model


def embed_chunks(chunks: list[dict]) -> np.ndarray:
    """
    Generate embeddings for a list of text chunks.

    Called once per document upload. We embed all chunks in a batch
    (more efficient than one at a time) and return a 2D numpy array.

    Args:
        chunks: List of chunk dicts from chunker.py
                Each must have a 'text' field.

    Returns:
        numpy array of shape (num_chunks, embedding_dim)
        e.g. for 50 chunks with all-MiniLM-L6-v2: shape is (50, 384)

    Why normalize?
        We use cosine similarity (how aligned are two vectors?).
        If vectors are L2-normalized (length = 1), then cosine similarity
        equals dot product. FAISS's IndexFlatIP computes dot products,
        so normalizing lets us use it for cosine similarity.
    """
    if not chunks:
        raise ValueError("Cannot embed an empty list of chunks.")

    model = get_embedding_model()

    # Extract just the text from each chunk dict
    texts = [chunk["text"] for chunk in chunks]

    logger.info(f"Embedding {len(texts)} chunks...")

    # encode() processes all texts in batches internally
    # show_progress_bar=True prints a progress bar (useful for large docs)
    # convert_to_numpy=True returns a numpy array instead of a PyTorch tensor
    embeddings = model.encode(
        texts,
        convert_to_numpy=True,
        show_progress_bar=len(texts) > 50,  # only show progress for large docs
        batch_size=32,  # process 32 texts at a time
    )

    # Normalize to unit length for cosine similarity via dot product
    embeddings = _normalize_vectors(embeddings)

    logger.info(
        f"Generated embeddings: shape={embeddings.shape}, "
        f"dtype={embeddings.dtype}"
    )

    return embeddings


def embed_query(question: str) -> np.ndarray:
    """
    Generate a single embedding for a user's question.

    Called each time the user asks a question. Fast because it's
    just one short text through the model.

    Args:
        question: The user's question string

    Returns:
        1D numpy array of shape (embedding_dim,) e.g. (384,)
        Normalized to unit length (same normalization as chunks).
    """
    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    model = get_embedding_model()

    # Encode single text — returns shape (1, 384), we squeeze to (384,)
    embedding = model.encode(
        [question.strip()],
        convert_to_numpy=True,
    )

    # Normalize (same as chunks — required for cosine similarity)
    embedding = _normalize_vectors(embedding)

    # Return 1D array: shape (384,) instead of (1, 384)
    return embedding[0]


def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """
    L2-normalize each vector in the array to unit length.

    L2 norm of a vector = sqrt(sum of squares of all elements)
    After normalization, each vector has length 1.0.

    Why does this matter?
        cosine_similarity(a, b) = dot(a, b) / (|a| * |b|)
        If |a| = |b| = 1, then cosine_similarity(a, b) = dot(a, b)
        This means we can use FAISS's fast dot-product search
        to get cosine similarity, which is what we actually want.

    Args:
        vectors: 2D array of shape (n, dim)

    Returns:
        Same shape, each row normalized to length 1.0
    """
    # Calculate the L2 norm of each vector (along axis=1 = per row)
    # keepdims=True preserves the 2D shape for broadcasting
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)

    # Avoid division by zero for any zero vectors
    norms = np.where(norms == 0, 1, norms)

    return (vectors / norms).astype(np.float32)
