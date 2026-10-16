"""
chunker.py — Text Chunking

Splits extracted PDF pages into smaller, overlapping text chunks.

Why chunk?
-----------
The embedding model converts text into a fixed-size vector (a list of numbers).
If you embed a 200-page document as a single vector, you lose all specificity.
The search can only match "this document" vs "not this document."

By splitting into chunks of ~800 characters, each vector represents a specific
topic or passage. The search then finds the few chunks most relevant to the
user's question — exactly what we need for RAG.

Why overlap?
------------
Imagine the answer to a question spans a chunk boundary:
    [...end of chunk 1: "The study concluded"] [chunk 2: "with significant results..."]

Without overlap, neither chunk alone contains the complete thought.
With overlap (chunk 2 starts partway through chunk 1), the context is preserved.

Chunk size trade-offs:
- Too small (< 200 chars): chunks lack enough context to be useful
- Too large (> 2000 chars): chunks are too broad, retrieval is less precise
- ~800 chars is a reasonable starting point for most documents

These settings are configurable in config.py.
"""

import re
import logging
from app.config import settings

logger = logging.getLogger(__name__)


def create_chunks(pages: list[dict], document_id: str) -> list[dict]:
    """
    Convert a list of extracted pages into a list of text chunks.

    Each chunk keeps a reference to its original page number so we can
    show "found on page X" in the citation UI.

    Args:
        pages:       Output from pdf_processor.extract_text_from_pdf()
                     Each item: {"page_number": int, "text": str, "char_count": int}
        document_id: The ID of the parent document (used in chunk metadata)

    Returns:
        List of chunk dictionaries:
        [
            {
                "chunk_id":    "doc123_chunk_0",
                "document_id": "doc123",
                "page_number": 3,
                "text":        "The study found that...",
                "char_count":  812,
            },
            ...
        ]
    """
    chunk_size = settings.chunk_size       # default: 800 characters
    chunk_overlap = settings.chunk_overlap  # default: 150 characters

    logger.info(
        f"Chunking {len(pages)} pages with "
        f"chunk_size={chunk_size}, overlap={chunk_overlap}"
    )

    all_chunks = []
    chunk_index = 0

    for page in pages:
        page_number = page["page_number"]
        page_text = page["text"]

        if not page_text.strip():
            continue  # skip empty pages

        # Split this page's text into chunks
        page_chunks = _split_text_into_chunks(
            text=page_text,
            chunk_size=chunk_size,
            overlap=chunk_overlap,
        )

        for chunk_text in page_chunks:
            chunk_text = chunk_text.strip()
            if len(chunk_text) < 20:
                # Skip fragments that are too short to be meaningful
                continue

            all_chunks.append({
                "chunk_id":    f"{document_id}_chunk_{chunk_index}",
                "document_id": document_id,
                "page_number": page_number,
                "text":        chunk_text,
                "char_count":  len(chunk_text),
            })
            chunk_index += 1

    logger.info(
        f"Created {len(all_chunks)} chunks from {len(pages)} pages "
        f"for document '{document_id}'"
    )

    return all_chunks


def _split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> list[str]:
    """
    Split a text string into overlapping chunks.

    Strategy:
    1. First try to split at paragraph boundaries (double newlines).
       This keeps related sentences together.
    2. If a paragraph is still too long, split at sentence boundaries.
    3. If a sentence is still too long, split at word boundaries.

    This produces more natural chunks than a hard character-count split.

    Args:
        text:       The text to split
        chunk_size: Target maximum characters per chunk
        overlap:    Characters to repeat at the start of the next chunk

    Returns:
        List of chunk text strings
    """
    if len(text) <= chunk_size:
        # Text fits in a single chunk — no splitting needed
        return [text]

    chunks = []
    # We track position by character index
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size

        if end >= text_length:
            # Last chunk — take everything remaining
            chunks.append(text[start:])
            break

        # Try to find a good split point — prefer paragraph, then sentence, then word
        split_pos = _find_split_position(text, start, end)

        chunks.append(text[start:split_pos].strip())

        # Move start forward, but back up by 'overlap' characters
        # so the next chunk shares some context with this one
        start = max(split_pos - overlap, start + 1)
        # The max(..., start + 1) prevents an infinite loop if split_pos == start

    return [c for c in chunks if c.strip()]  # remove any empty strings


def _find_split_position(text: str, start: int, end: int) -> int:
    """
    Find the best position to split text, looking backwards from 'end'.

    Priority:
    1. Double newline (paragraph break)
    2. Period/question mark/exclamation followed by space (sentence end)
    3. Single newline
    4. Space (word boundary)
    5. Hard cut at 'end' (last resort)

    Args:
        text:  Full text string
        start: Current chunk start position
        end:   Desired chunk end position

    Returns:
        The position (index) to split at
    """
    # Search window: look backwards up to 20% of chunk_size
    search_window = max(end - (end - start) // 5, start + 1)

    # 1. Try paragraph break
    pos = text.rfind("\n\n", search_window, end)
    if pos != -1:
        return pos + 2  # include the newlines in the current chunk

    # 2. Try sentence boundary (. ! ? followed by space or newline)
    for i in range(end, search_window - 1, -1):
        if i < len(text) and text[i - 1] in ".!?" and (i >= len(text) or text[i] in " \n"):
            return i

    # 3. Try single newline
    pos = text.rfind("\n", search_window, end)
    if pos != -1:
        return pos + 1

    # 4. Try word boundary (space)
    pos = text.rfind(" ", search_window, end)
    if pos != -1:
        return pos + 1

    # 5. Hard cut — no natural boundary found
    return end


def get_chunk_stats(chunks: list[dict]) -> dict:
    """
    Return basic statistics about the chunks.
    Useful for debugging and understanding document structure.
    """
    if not chunks:
        return {"count": 0, "avg_chars": 0, "min_chars": 0, "max_chars": 0}

    char_counts = [c["char_count"] for c in chunks]

    return {
        "count":     len(chunks),
        "avg_chars": round(sum(char_counts) / len(char_counts)),
        "min_chars": min(char_counts),
        "max_chars": max(char_counts),
        "pages_covered": len(set(c["page_number"] for c in chunks)),
    }
