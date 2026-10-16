"""
schemas.py — Pydantic Data Models (Request/Response Contracts)

Pydantic models serve two purposes here:
1. REQUEST validation — FastAPI checks incoming data against these models
   automatically. If a required field is missing or the wrong type,
   FastAPI returns a 422 error with a clear explanation before your
   handler function even runs.

2. RESPONSE documentation — FastAPI reads these models to generate the
   /docs Swagger page, showing exactly what each endpoint returns.

Think of them as typed dictionaries with built-in validation.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─────────────────────────────────────────────────────────────
# Document Upload Response
# ─────────────────────────────────────────────────────────────

class DocumentUploadResponse(BaseModel):
    """
    Returned by POST /api/documents/upload after successful processing.
    """
    document_id: str = Field(
        description="Unique ID assigned to this document. Use it in /api/chat requests."
    )
    filename: str = Field(
        description="Original filename of the uploaded PDF."
    )
    page_count: int = Field(
        description="Total number of pages extracted from the PDF."
    )
    chunk_count: int = Field(
        description="Number of text chunks created from the document."
    )
    status: str = Field(
        default="ready",
        description="Processing status: 'ready' means the document is indexed and searchable."
    )
    message: str = Field(
        default="Document processed successfully.",
        description="Human-readable status message."
    )


# ─────────────────────────────────────────────────────────────
# Chat / Question-Answer
# ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """
    Request body for POST /api/chat.
    """
    document_id: str = Field(
        description="The document_id returned by the upload endpoint."
    )
    question: str = Field(
        min_length=1,
        max_length=2000,
        description="The user's question. Must be between 1 and 2000 characters."
    )


class SourceChunk(BaseModel):
    """
    A single retrieved source passage included in a chat response.

    This comes from the actual PDF — NOT from the LLM's imagination.
    The page number is taken from the chunk's metadata (set during chunking),
    not from anything the LLM generated.
    """
    page: int = Field(
        description="Original PDF page number where this text was found."
    )
    text: str = Field(
        description="The retrieved text passage from the document."
    )
    score: float = Field(
        description="Cosine similarity score between this chunk and the question (0.0–1.0)."
    )


class ChatResponse(BaseModel):
    """
    Response from POST /api/chat.
    """
    answer: str = Field(
        description=(
            "AI-generated response based on retrieved document passages; "
            "verify important answers against the supplied sources."
        )
    )
    sources: list[SourceChunk] = Field(
        default=[],
        description="The retrieved passages used as evidence for the answer."
    )
    grounded: bool = Field(
        description=(
            "True when the model did not decline for insufficient evidence and "
            "retrieved passages met the configured relevance threshold."
        )
    )


# ─────────────────────────────────────────────────────────────
# Document Summary
# ─────────────────────────────────────────────────────────────

class SummaryResponse(BaseModel):
    """
    Response from POST /api/documents/{document_id}/summary.
    """
    summary: str = Field(
        description="A concise summary of the document's content."
    )
    sources: list[SourceChunk] = Field(
        default=[],
        description="The document chunks used to generate the summary."
    )


# ─────────────────────────────────────────────────────────────
# Document Deletion
# ─────────────────────────────────────────────────────────────

class DeleteResponse(BaseModel):
    """
    Response from DELETE /api/documents/{document_id}.
    """
    message: str
    document_id: str


# ─────────────────────────────────────────────────────────────
# Error Response
# ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """
    Standard error shape returned by all endpoints on failure.
    FastAPI uses 'detail' by default for HTTPException messages,
    so we match that convention.
    """
    detail: str
