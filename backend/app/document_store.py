"""
document_store.py — In-Memory Document Registry

This module is the application's short-term memory.
It stores all currently loaded documents and their FAISS indexes.

Why in-memory?
--------------
For our first version, we don't need a database. Documents are
processed on upload and held in RAM until:
- The user clicks "Remove Document"
- The server restarts

Trade-offs:
- Simple to implement and understand
- No database setup required
- Fast (RAM is faster than disk)
- BUT: documents are lost on server restart
- BUT: not suitable for multiple simultaneous users in production

For a production app, you'd store indexes on disk or use a vector
database like Pinecone, Weaviate, or Chroma.

Thread safety note:
-------------------
Python's GIL (Global Interpreter Lock) and FastAPI's async model
mean that simple dict operations are effectively safe here.
For production multi-worker deployments, you'd need shared storage.
"""

import uuid
import logging
from datetime import datetime
from dataclasses import dataclass, field
from app.vector_store import DocumentIndex

logger = logging.getLogger(__name__)


@dataclass
class StoredDocument:
    """
    Complete record for an uploaded and processed document.
    Stored in the in-memory registry.
    """
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    doc_index: DocumentIndex       # FAISS index + chunk metadata
    uploaded_at: datetime = field(default_factory=datetime.now)
    status: str = "ready"


class DocumentStore:
    """
    Thread-safe in-memory store for processed documents.

    Usage:
        store = DocumentStore()                    # create once at app level
        doc_id = store.add(document_record)        # add a document
        doc = store.get(doc_id)                    # retrieve it
        store.remove(doc_id)                       # delete it
        all_docs = store.list_all()                # see all documents
    """

    def __init__(self):
        # dict mapping document_id (str) → StoredDocument
        self._documents: dict[str, StoredDocument] = {}
        logger.info("DocumentStore initialized (in-memory)")

    def generate_id(self) -> str:
        """
        Generate a unique document ID.

        We use UUID4 (random UUID) rather than sequential numbers or
        user-provided IDs. This prevents:
        - ID collisions between documents
        - Users guessing other documents' IDs
        - Path traversal attacks (a user can't request "../secrets")
        """
        return str(uuid.uuid4())

    def add(self, stored_doc: StoredDocument) -> str:
        """
        Add a processed document to the store.

        Args:
            stored_doc: A StoredDocument instance with all fields populated

        Returns:
            The document_id (same as stored_doc.document_id)
        """
        doc_id = stored_doc.document_id
        self._documents[doc_id] = stored_doc
        logger.info(
            f"Document added to store: id={doc_id}, "
            f"pages={stored_doc.page_count}, chunks={stored_doc.chunk_count}"
        )
        return doc_id

    def get(self, document_id: str) -> StoredDocument | None:
        """
        Retrieve a document by ID.

        Returns None (not an exception) if not found.
        The caller decides whether to raise a 404 error.
        """
        return self._documents.get(document_id)

    def remove(self, document_id: str) -> bool:
        """
        Remove a document and free its memory.

        Args:
            document_id: ID of the document to remove

        Returns:
            True if the document existed and was removed,
            False if it didn't exist (not an error — idempotent)
        """
        if document_id in self._documents:
            self._documents.pop(document_id)
            logger.info(
                f"Document removed from store: id={document_id}"
            )
            # The DocumentIndex (with its FAISS index) is now garbage-collected
            # Python's reference counting will free that memory automatically
            return True

        logger.warning(f"Attempted to remove non-existent document: id={document_id}")
        return False

    def exists(self, document_id: str) -> bool:
        """Check if a document ID is currently in the store."""
        return document_id in self._documents

    def list_all(self) -> list[dict]:
        """
        Return summary info for all stored documents.
        Does not include the FAISS index or chunk data (too large).
        """
        return [
            {
                "document_id": doc.document_id,
                "filename": doc.filename,
                "page_count": doc.page_count,
                "chunk_count": doc.chunk_count,
                "status": doc.status,
                "uploaded_at": doc.uploaded_at.isoformat(),
            }
            for doc in self._documents.values()
        ]

    @property
    def count(self) -> int:
        """Number of documents currently in the store."""
        return len(self._documents)


# ─────────────────────────────────────────────────────────────
# Application-level singleton
# ─────────────────────────────────────────────────────────────
# This single instance is imported by main.py and all routes.
# Because Python caches module imports, every file that does
#     from app.document_store import document_store
# gets the SAME instance. This is how we share state across
# the application without a database.

document_store = DocumentStore()
