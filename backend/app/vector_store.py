"""
vector_store.py — FAISS Vector Index

What is FAISS?
--------------
FAISS (Facebook AI Similarity Search) is a library for searching
through large collections of vectors efficiently.

In our RAG pipeline:
1. We embed each document chunk as a vector (a list of 384 numbers).
2. We add those vectors to a FAISS index.
3. When the user asks a question, we embed the question too.
4. We ask FAISS: "which stored vectors are most similar to this question vector?"
5. FAISS returns the top-k most similar chunk indices.
6. We look up the original chunk text for those indices.

Why is this better than keyword search?
----------------------------------------
Keyword search: "machine learning" only matches documents containing
those exact words.

Semantic search: "machine learning" also matches "neural networks",
"deep learning", "AI models" — because they're semantically related.
The vectors capture meaning, not just words.

Index type: IndexFlatIP
------------------------
- "Flat" = no compression, exact search (perfect accuracy, fine for small docs)
- "IP" = Inner Product (which equals cosine similarity for normalized vectors)
- For production with millions of documents, you'd use approximate indexes
  (IndexIVFFlat, IndexHNSW) that trade some accuracy for speed.
  For our use case (hundreds to thousands of chunks), exact search is fine.

One index per document:
------------------------
Each uploaded document gets its own FAISS index stored in memory.
This means questions always search only the currently relevant document,
not all documents ever uploaded.
"""

import numpy as np
import faiss
import logging
from dataclasses import dataclass, field
from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentIndex:
    """
    Holds everything needed to search a single document.

    We keep:
    - The FAISS index (for fast vector search)
    - The original chunk metadata (to retrieve text and page numbers)

    These two structures must stay in sync:
    - Vector at index position i corresponds to chunk metadata at position i
    - If we add 50 chunks, we have 50 vectors and 50 metadata entries
    """
    document_id: str
    faiss_index: faiss.IndexFlatIP  # the actual FAISS index object
    chunks: list[dict] = field(default_factory=list)  # original chunk dicts
    embedding_dim: int = 384  # dimension of each vector


def build_index(chunks: list[dict], embeddings: np.ndarray, document_id: str) -> DocumentIndex:
    """
    Build a FAISS index from chunk embeddings.

    Called once per document upload, after embed_chunks() runs.

    Args:
        chunks:      List of chunk dicts (from chunker.py)
        embeddings:  2D numpy array of shape (num_chunks, embedding_dim)
        document_id: The document's unique ID

    Returns:
        DocumentIndex object containing the FAISS index and chunk metadata
    """
    if len(chunks) == 0:
        raise ValueError("Cannot build an index with no chunks.")

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings."
        )

    # Get the embedding dimension from the actual data
    embedding_dim = embeddings.shape[1]
    logger.info(
        f"Building FAISS index for document '{document_id}': "
        f"{len(chunks)} vectors of dimension {embedding_dim}"
    )

    # Create the FAISS index
    # IndexFlatIP = exact inner-product (cosine similarity for normalized vectors)
    # The parameter is the vector dimension (384 for all-MiniLM-L6-v2)
    index = faiss.IndexFlatIP(embedding_dim)

    # Ensure embeddings are float32 — FAISS requires this exact type
    embeddings_f32 = embeddings.astype(np.float32)

    # Add all vectors to the index in one batch
    # FAISS assigns implicit IDs: 0, 1, 2, ... matching the order we add them
    index.add(embeddings_f32)

    logger.info(f"FAISS index built. Total vectors: {index.ntotal}")

    return DocumentIndex(
        document_id=document_id,
        faiss_index=index,
        chunks=chunks,
        embedding_dim=embedding_dim,
    )


def search_index(
    doc_index: DocumentIndex,
    query_embedding: np.ndarray,
    top_k: int | None = None,
) -> list[dict]:
    """
    Search the FAISS index for chunks most similar to the query.

    Args:
        doc_index:       The DocumentIndex to search
        query_embedding: 1D array of shape (embedding_dim,) — the question vector
        top_k:           How many results to return (default: from config)

    Returns:
        List of result dicts, sorted by score (highest first):
        [
            {
                "chunk_id":    "doc123_chunk_7",
                "document_id": "doc123",
                "page_number": 4,
                "text":        "The study found...",
                "char_count":  812,
                "score":       0.87,  # cosine similarity (higher = more relevant)
            },
            ...
        ]
        Scores range from 0.0 (unrelated) to 1.0 (identical meaning).
    """
    if top_k is None:
        top_k = settings.top_k_chunks  # default: 3

    if doc_index.faiss_index.ntotal == 0:
        logger.warning("Attempted to search an empty FAISS index.")
        return []

    # Clamp top_k to available vectors (can't retrieve more than we have)
    actual_k = min(top_k, doc_index.faiss_index.ntotal)

    # FAISS expects a 2D array: (num_queries, embedding_dim)
    # Our query is 1D shape (384,), so we reshape to (1, 384)
    query_2d = query_embedding.reshape(1, -1).astype(np.float32)

    # Run the search
    # Returns two arrays:
    # - distances: shape (1, k) — similarity scores for each result
    # - indices:   shape (1, k) — positions in the index for each result
    distances, indices = doc_index.faiss_index.search(query_2d, actual_k)

    # Extract the results for the first (only) query
    raw_distances = distances[0]
    raw_indices = indices[0]

    results = []
    for score, idx in zip(raw_distances, raw_indices):
        # FAISS returns -1 for unfilled slots (happens when k > ntotal)
        if idx == -1:
            continue

        # Look up the original chunk metadata by its index position
        chunk = doc_index.chunks[idx]

        results.append({
            **chunk,                   # all original chunk fields
            "score": float(score),     # similarity score as Python float
        })

    # Sort by score descending (highest similarity first)
    results.sort(key=lambda x: x["score"], reverse=True)

    logger.info(
        f"Search returned {len(results)} results. "
        f"Top score: {results[0]['score']:.3f}" if results else "Search returned no results."
    )

    return results


def filter_by_relevance(results: list[dict], threshold: float | None = None) -> list[dict]:
    """
    Filter search results to only those above the relevance threshold.

    This prevents low-quality matches from being sent to the LLM.
    If no results pass the threshold, the RAG pipeline will respond
    with "I couldn't find that information in the document."

    Args:
        results:   Results from search_index()
        threshold: Minimum score (default: from config)

    Returns:
        Filtered list of results
    """
    if threshold is None:
        threshold = settings.relevance_threshold

    filtered = [r for r in results if r["score"] >= threshold]

    if len(filtered) < len(results):
        logger.info(
            f"Relevance filter: {len(results)} results → {len(filtered)} "
            f"above threshold {threshold}"
        )

    return filtered
