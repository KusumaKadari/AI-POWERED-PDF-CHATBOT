"""
main.py — FastAPI Application Entry Point

Registers all routes and configures middleware.
The actual logic lives in the individual modules (pdf_processor, chunker, etc.)
— main.py just wires them together into HTTP endpoints.
"""

# Suppress TensorFlow import inside transformers/sentence-transformers.
# We only use the PyTorch backend. These must be set before any ML imports.
import os
os.environ["USE_TF"] = "0"
os.environ["TRANSFORMERS_NO_TF"] = "1"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.schemas import (
    DocumentUploadResponse,
    ChatRequest,
    ChatResponse,
    SummaryResponse,
    DeleteResponse,
)
from app.pdf_processor import extract_text_from_pdf, PDFProcessingError
from app.chunker import create_chunks
from app.embeddings import embed_chunks
from app.vector_store import build_index
from app.document_store import document_store, StoredDocument
from app.rag_pipeline import answer_question, summarize_document

# Configure logging — shows timestamps and log levels in the terminal
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Lifespan: startup/shutdown events
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Keep startup lightweight; load the configured embedding model on first upload.
    """
    logger.info("DocuMind API starting up...")
    logger.info("Embedding model will load when the first PDF is uploaded.")
    yield
    # Shutdown code would go here (nothing needed for now)
    logger.info("DocuMind API shutting down.")


# ─────────────────────────────────────────────────────────────
# FastAPI app instance
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="DocuMind API",
    description="AI-Powered PDF Research Assistant — RAG pipeline backend",
    version="0.1.0",
    lifespan=lifespan,
)

# ─────────────────────────────────────────────────────────────
# CORS — allow the React dev server to call this API
# ─────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Verify the backend is running and return configuration info."""
    return {
        "status": "ok",
        "message": "DocuMind backend is running",
        "embedding_model": settings.embedding_model,
        "generation_provider": "Google Gemini",
        "generation_model": settings.gemini_model,
        "documents_loaded": document_store.count,
    }


@app.get("/", tags=["Root"])
async def root():
    return {"message": "Welcome to DocuMind API", "docs": "/docs", "health": "/api/health"}


# ─────────────────────────────────────────────────────────────
# Document Upload
# ─────────────────────────────────────────────────────────────

@app.post(
    "/api/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Documents"],
    summary="Upload and process a PDF document",
)
async def upload_document(
    file: UploadFile = File(..., description="PDF file to process"),
):
    """
    Upload a PDF, extract text, create chunks, generate embeddings,
    and build a FAISS index ready for question answering.

    Pipeline:
    1. Validate file type and size
    2. Extract text page by page (PyMuPDF)
    3. Split into overlapping chunks (chunker)
    4. Generate embeddings (Sentence Transformers)
    5. Build FAISS index (vector_store)
    6. Store in memory (document_store)
    7. Return document ID and stats
    """

    # ── Step 1: Enforce the single-document memory limit ────────
    if document_store.count >= settings.max_loaded_documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One document can be loaded at a time. Remove the current document first.",
        )

    # ── Step 2: Validate filename and read no more than the limit ─
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted. Please upload a .pdf file.",
        )

    try:
        file_bytes = await file.read(settings.max_upload_size + 1)
    finally:
        await file.close()

    if len(file_bytes) > settings.max_upload_size:
        size_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"File too large: {size_mb:.1f} MB. "
                f"Maximum allowed size is {settings.max_upload_size // (1024*1024)} MB."
            ),
        )

    if len(file_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if document_store.count >= settings.max_loaded_documents:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One document can be loaded at a time. Remove the current document first.",
        )

    original_filename = filename
    logger.info(f"PDF upload received ({len(file_bytes):,} bytes)")

    # ── Step 3: Extract text from PDF ──────────────────────────
    try:
        pages = extract_text_from_pdf(file_bytes, filename=original_filename)
    except PDFProcessingError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error during PDF extraction: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while processing the PDF.",
        )

    # ── Step 4: Generate a unique document ID ──────────────────
    document_id = str(uuid.uuid4())
    logger.info(f"Assigned document ID: {document_id}")

    # ── Step 5: Chunk the text ──────────────────────────────────
    chunks = create_chunks(pages, document_id=document_id)

    if not chunks:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Could not extract any usable text chunks from the document.",
        )

    # ── Step 6: Generate embeddings ────────────────────────────
    try:
        embeddings = embed_chunks(chunks)
    except Exception as e:
        logger.error(f"Embedding generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate document embeddings.",
        )

    # ── Step 7: Build FAISS index ───────────────────────────────
    try:
        doc_index = build_index(chunks, embeddings, document_id=document_id)
    except Exception as e:
        logger.error(f"FAISS index build failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to build the search index.",
        )

    # ── Step 8: Store in memory ─────────────────────────────────
    stored_doc = StoredDocument(
        document_id=document_id,
        filename=original_filename,
        page_count=len(pages),
        chunk_count=len(chunks),
        doc_index=doc_index,
    )
    document_store.add(stored_doc)

    logger.info(
        f"Document ready: id={document_id}, pages={len(pages)}, chunks={len(chunks)}"
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=original_filename,
        page_count=len(pages),
        chunk_count=len(chunks),
        status="ready",
        message=f"Successfully processed '{original_filename}'.",
    )


# ─────────────────────────────────────────────────────────────
# Document Deletion
# ─────────────────────────────────────────────────────────────

@app.delete(
    "/api/documents/{document_id}",
    response_model=DeleteResponse,
    tags=["Documents"],
    summary="Remove a document and its index from memory",
)
async def delete_document(document_id: str):
    """
    Remove a document's FAISS index and metadata from memory.
    After deletion, questions about this document will return 404.
    """
    removed = document_store.remove(document_id)

    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    return DeleteResponse(
        message="Document removed successfully.",
        document_id=document_id,
    )


# ─────────────────────────────────────────────────────────────
# Chat — placeholder until Phase 5 (LLM integration)
# ─────────────────────────────────────────────────────────────

@app.post(
    "/api/chat",
    response_model=ChatResponse,
    tags=["Chat"],
    summary="Ask a question about a processed document",
)
async def chat(request: ChatRequest):
    """
    Full RAG pipeline:
    1. Validate document exists
    2. Embed the question
    3. Search FAISS for relevant chunks
    4. Filter by relevance threshold
    5. Build grounded prompt
    6. Generate an answer with the configured LLM provider
    7. Return answer + source passages with page numbers
    """
    # Validate document exists
    stored_doc = document_store.get(request.document_id)
    if not stored_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Document '{request.document_id}' not found. "
                "Please upload a document first."
            ),
        )

    # Validate question
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question cannot be empty.",
        )

    # Run the RAG pipeline
    try:
        result = answer_question(
            question=question,
            doc_index=stored_doc.doc_index,
        )
    except ValueError as e:
        # Configuration errors (such as a missing Gemini API key).
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        )
    except RuntimeError as e:
        # Provider errors, including Gemini quota or availability failures.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Unexpected error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the answer.",
        )

    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        grounded=result["grounded"],
    )


# ─────────────────────────────────────────────────────────────
# Summary — placeholder until Phase 5
# ─────────────────────────────────────────────────────────────

@app.post(
    "/api/documents/{document_id}/summary",
    response_model=SummaryResponse,
    tags=["Documents"],
    summary="Generate a summary of the document",
)
async def summarize_document_endpoint(document_id: str):
    """
    Generate a document summary using sampled chunks and the configured LLM.
    """
    stored_doc = document_store.get(document_id)
    if not stored_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' not found.",
        )

    try:
        result = summarize_document(
            doc_index=stored_doc.doc_index,
            filename=stored_doc.filename,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        logger.error(f"Summary error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary.",
        )

    return SummaryResponse(
        summary=result["summary"],
        sources=result["sources"],
    )
