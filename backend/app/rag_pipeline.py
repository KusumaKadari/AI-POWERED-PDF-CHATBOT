"""
rag_pipeline.py — Retrieval-Augmented Generation Pipeline

This is the core of DocuMind. It orchestrates the full RAG workflow:

    User question
        ↓
    1. Embed the question (embeddings.py)
        ↓
    2. Search FAISS index for relevant chunks (vector_store.py)
        ↓
    3. Filter chunks by relevance score (vector_store.py)
        ↓
    4. If no relevant chunks → return "not found" message
        ↓
    5. Build a grounded prompt (prompts.py)
        ↓
    6. Send prompt to the configured text-generation provider
        ↓
    7. Return answer + source passages

What is RAG and why use it?
-----------------------------
A plain LLM (like Gemini) knows what it was trained on, but doesn't know
what's in YOUR specific PDF. RAG solves this by:
1. Retrieving relevant passages from your document (the "R" in RAG)
2. Adding them as context in the prompt (the "A" — Augmented)
3. Asking the LLM to answer based on that context (the "G" — Generation)

This grounds the answer in your actual document rather than the model's
general training data.
"""

import logging
import time

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import settings
from app.embeddings import embed_query
from app.vector_store import search_index, filter_by_relevance, DocumentIndex
from app.prompts import (
    build_qa_prompt,
    build_summary_prompt,
    build_insufficient_evidence_response,
)

logger = logging.getLogger(__name__)

# Module-level Gemini client — configured once, reused for all requests
_gemini_model = None


def get_gemini_model():
    """
    Initialize and return the Gemini generative model.
    Uses lazy initialization — created on first call, reused after.

    Raises:
        ValueError: if GEMINI_API_KEY is not set
        Exception:  if the Gemini API is unreachable
    """
    global _gemini_model

    if _gemini_model is None:
        api_key = settings.gemini_api_key

        if not api_key.strip() or api_key.strip().lower() == "your_gemini_api_key_here":
            raise ValueError(
                "GEMINI_API_KEY is not set. "
                "Add your API key to backend/.env: GEMINI_API_KEY=your_key_here"
            )

        # Configure the SDK with the API key
        genai.configure(api_key=api_key)

        # Create the model instance
        # generation_config controls how the model generates text:
        # - temperature: 0.2 = more focused/deterministic (0.0=deterministic, 1.0=creative)
        #   For RAG we want low temperature — we need factual, grounded answers
        # - max_output_tokens: limits response length
        _gemini_model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                max_output_tokens=1024,
            ),
        )

        logger.info(f"Gemini model initialized: {settings.gemini_model}")

    return _gemini_model


def answer_question(
    question: str,
    doc_index: DocumentIndex,
) -> dict:
    """
    Run the full RAG pipeline for a single question.

    Args:
        question:  The user's question string
        doc_index: The FAISS index for the uploaded document

    Returns:
        dict with:
        - answer:   str   — the generated answer
        - sources:  list  — retrieved chunks with page numbers and scores
        - grounded: bool  — True if answer is based on sufficient evidence
    """
    logger.info("RAG pipeline started (question length: %s characters).", len(question))

    # ── Step 1: Embed the question ───────────────────────────────
    try:
        query_embedding = embed_query(question)
    except Exception as e:
        logger.error(f"Failed to embed question: {e}")
        raise RuntimeError(f"Could not process your question: {e}")

    # ── Step 2: Search FAISS for relevant chunks ─────────────────
    raw_results = search_index(
        doc_index=doc_index,
        query_embedding=query_embedding,
        top_k=settings.top_k_chunks,
    )

    # ── Step 3: Filter by relevance threshold ────────────────────
    relevant_chunks = filter_by_relevance(
        results=raw_results,
        threshold=settings.relevance_threshold,
    )

    # ── Step 4: Handle insufficient evidence ─────────────────────
    if not relevant_chunks:
        logger.info(
            f"No chunks passed relevance threshold ({settings.relevance_threshold}). "
            f"Top raw score was: {raw_results[0]['score']:.3f}" if raw_results else
            "No results returned from FAISS."
        )
        return {
            "answer": build_insufficient_evidence_response(),
            "sources": _format_sources(raw_results[:2]),  # show top 2 even if below threshold
            "grounded": False,
        }

    # ── Step 5: Build the grounded prompt ────────────────────────
    prompt = build_qa_prompt(
        question=question,
        context_chunks=relevant_chunks,
    )

    # ── Step 6: Generate an answer with the configured provider ──
    try:
        answer_text = _generate_text(prompt)
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Text generation failed: {e}")
        raise RuntimeError(f"Failed to generate answer: {e}")

    # ── Step 7: Return answer with sources ───────────────────────
    logger.info(f"RAG pipeline complete. Answer length: {len(answer_text)} chars")

    return {
        "answer": answer_text,
        "sources": _format_sources(relevant_chunks),
        "grounded": not _is_insufficient_answer(answer_text),
    }


def summarize_document(doc_index: DocumentIndex, filename: str = "the document") -> dict:
    """
    Generate a summary of the document using a representative sample of chunks.

    For long documents we can't send every chunk to the LLM — it would
    exceed the context window and cost too many tokens. Instead we:
    1. Take the first few chunks (document intro/abstract)
    2. Take some middle chunks (body content)
    3. Take the last few chunks (conclusions)

    We tell the model explicitly that this is a sampled summary.

    Args:
        doc_index: The document's FAISS index (contains all chunks)
        filename:  Original filename for the prompt

    Returns:
        dict with: summary (str), sources (list)
    """
    all_chunks = doc_index.chunks

    if not all_chunks:
        return {
            "summary": "No content available to summarize.",
            "sources": [],
        }

    # Sample representative chunks
    # For short documents (≤15 chunks) use all of them
    # For longer documents, sample from beginning, middle, and end
    if len(all_chunks) <= 15:
        sample_chunks = all_chunks
    else:
        n = len(all_chunks)
        first = all_chunks[:4]                        # introduction
        middle = all_chunks[n//2 - 2 : n//2 + 2]    # middle content
        last = all_chunks[-4:]                        # conclusions
        sample_chunks = first + middle + last

        # Remove duplicates (can happen with very short documents)
        seen = set()
        unique_chunks = []
        for c in sample_chunks:
            if c["chunk_id"] not in seen:
                seen.add(c["chunk_id"])
                unique_chunks.append(c)
        sample_chunks = unique_chunks

    # Build summary prompt
    prompt = build_summary_prompt(sample_chunks, filename=filename)

    # Generate the summary with the configured provider.
    try:
        summary_text = _generate_text(prompt)
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise RuntimeError(f"Failed to generate summary: {e}")

    return {
        "summary": summary_text,
        "sources": _format_sources(sample_chunks),
    }


def _generate_text(prompt: str) -> str:
    """Generate text with the configured Gemini cloud model."""
    return _call_gemini(prompt)


def _call_gemini(prompt: str) -> str:
    """
    Send a prompt to the Gemini API and return the response text.

    Args:
        prompt: The complete prompt string

    Returns:
        The model's response text

    Raises:
        RuntimeError: on API errors, rate limits, or empty responses
    """
    try:
        model = get_gemini_model()
    except ValueError:
        raise
    except Exception as e:
        raise RuntimeError(_safe_gemini_error_message(e)) from e

    max_retries = 2

    for attempt in range(max_retries + 1):
        try:
            response = model.generate_content(prompt)
            if not response.candidates:
                raise RuntimeError(
                    "Gemini returned no answer. The request may have been blocked."
                )

            answer = response.text
            if not answer or not answer.strip():
                raise RuntimeError("Gemini returned an empty answer.")
            return answer.strip()
        except Exception as e:
            if isinstance(e, RuntimeError):
                raise

            message = _safe_gemini_error_message(e)
            retryable = _is_transient_gemini_error(e)
            if retryable and attempt < max_retries:
                wait_seconds = 2 ** attempt
                logger.warning(
                    "Transient Gemini error; retrying attempt %s of %s in %s second(s).",
                    attempt + 1,
                    max_retries,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue

            raise RuntimeError(message) from e

    raise RuntimeError("Gemini could not generate an answer. Please try again later.")


def _safe_gemini_error_message(error: Exception) -> str:
    """Map provider failures to user-safe messages without returning raw details."""
    detail = str(error).lower()
    error_type = type(error).__name__.lower()

    if isinstance(error, google_exceptions.Unauthenticated) or any(
        marker in detail
        for marker in ("invalid api key", "api key not valid", "api_key_invalid", "401")
    ):
        return "Gemini rejected the API key. Check GEMINI_API_KEY in backend/.env."

    if isinstance(error, google_exceptions.NotFound) or (
        "model" in detail and any(word in detail for word in ("not found", "unsupported"))
    ):
        return (
            f"Gemini model '{settings.gemini_model}' is unavailable. "
            "Check GEMINI_MODEL in backend/.env."
        )

    quota_markers = ("quota", "billing", "credits exhausted", "daily limit")
    if any(marker in detail for marker in quota_markers) or isinstance(
        error, google_exceptions.ResourceExhausted
    ):
        return (
            "Gemini API quota or credits are exhausted. Check your Google AI "
            "Studio quota and billing status, then try again after it resets."
        )

    if isinstance(error, google_exceptions.TooManyRequests):
        return "Gemini is temporarily rate-limiting requests. Please wait briefly and try again."

    if isinstance(error, google_exceptions.PermissionDenied):
        return (
            "Gemini denied this request. Check that the API key is valid and "
            "has access to the configured model."
        )

    if isinstance(error, google_exceptions.InvalidArgument):
        return "Gemini rejected the request. Check the configured model and request settings."

    if isinstance(
        error,
        (
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded,
            google_exceptions.InternalServerError,
            ConnectionError,
            TimeoutError,
        ),
    ) or any(
        word in error_type
        for word in (
            "connection",
            "timeout",
            "serviceunavailable",
            "internalservererror",
            "badgateway",
            "gatewaytimeout",
        )
    ):
        return "Could not reach Gemini. Check your internet connection and try again."

    cause = error.__cause__ or error.__context__
    for _ in range(3):
        if cause is None:
            break
        cause_type = type(cause).__name__.lower()
        if isinstance(cause, (ConnectionError, TimeoutError)) or any(
            word in cause_type for word in ("connection", "timeout")
        ):
            return "Could not reach Gemini. Check your internet connection and try again."
        cause = cause.__cause__ or cause.__context__

    return "Gemini could not generate an answer. Check the API key and model configuration."


def _is_transient_gemini_error(error: Exception) -> bool:
    """Retry only temporary rate limits and transient provider/network failures."""
    current_error: BaseException | None = error
    quota_markers = ("quota", "billing", "credits exhausted", "daily limit")

    for _ in range(4):
        if current_error is None:
            break
        detail = str(current_error).lower()
        if any(marker in detail for marker in quota_markers) or isinstance(
            current_error, google_exceptions.ResourceExhausted
        ):
            return False
        error_type = type(current_error).__name__.lower()
        if isinstance(
            current_error,
            (
                google_exceptions.TooManyRequests,
                google_exceptions.ServiceUnavailable,
                google_exceptions.DeadlineExceeded,
                google_exceptions.InternalServerError,
                ConnectionError,
                TimeoutError,
            ),
        ) or any(word in error_type for word in ("connection", "timeout")):
            return True
        current_error = current_error.__cause__ or current_error.__context__

    return False


def _is_insufficient_answer(answer: str) -> bool:
    """Recognize the prompt's explicit no-evidence answer without claiming support."""
    return answer.strip().lower().startswith(
        "i couldn't find that information in the uploaded document"
    )


def _format_sources(chunks: list[dict]) -> list[dict]:
    """
    Format raw chunk dicts into the clean SourceChunk shape
    expected by the ChatResponse schema.

    Deduplicates chunks from the same page that have nearly identical text
    to avoid showing the same source twice.

    Args:
        chunks: List of chunk dicts (with 'page_number', 'text', 'score')

    Returns:
        List of source dicts: [{"page": int, "text": str, "score": float}]
    """
    seen_pages = {}
    sources = []

    for chunk in chunks:
        page = chunk["page_number"]
        score = chunk.get("score", 0.0)
        text = chunk["text"]

        # If we've seen this page before, keep the higher-scoring chunk
        if page in seen_pages:
            if score > seen_pages[page]["score"]:
                seen_pages[page] = {"page": page, "text": text, "score": score}
        else:
            seen_pages[page] = {"page": page, "text": text, "score": score}

    # Sort by page number for a consistent, readable order
    sources = sorted(seen_pages.values(), key=lambda x: x["page"])

    return sources
