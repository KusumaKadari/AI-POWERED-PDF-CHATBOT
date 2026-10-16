"""
pdf_processor.py — PDF Text Extraction

Uses PyMuPDF (imported as 'fitz') to read PDF files and extract
text from each page individually.

Why PyMuPDF?
- Fast and accurate text extraction
- Preserves reading order better than many alternatives
- Gives us page-level access (page 1, page 2, etc.)
- Handles most PDF variants well
- Pure Python, no external binaries needed

What we extract:
- The text content of each page
- The page number (1-indexed to match what users see in their PDF viewer)

What we do NOT handle here (future enhancements):
- Scanned PDFs (images of text) — need OCR like Tesseract
- Tables with complex layouts
- Mathematical formulas
- Text inside images
"""

import fitz  # PyMuPDF — the import name is 'fitz' for historical reasons
import logging

logger = logging.getLogger(__name__)


class PDFProcessingError(Exception):
    """Raised when PDF extraction fails for a known reason."""
    pass


def extract_text_from_pdf(file_bytes: bytes, filename: str = "document.pdf") -> list[dict]:
    """
    Extract text from a PDF file given its raw bytes.

    Why bytes instead of a file path?
    FastAPI gives us the file content as bytes in memory.
    Using bytes avoids writing a temp file to disk, which is cleaner
    and more secure (no leftover files if something crashes).

    Args:
        file_bytes: Raw PDF content as bytes
        filename:   Original filename, used only for logging

    Returns:
        A list of page dictionaries, one per page:
        [
            {
                "page_number": 1,      # 1-indexed (matches PDF viewer)
                "text": "The text...", # extracted text for this page
                "char_count": 1234,    # character count (useful for debugging)
            },
            ...
        ]

    Raises:
        PDFProcessingError: if the file is not a valid PDF,
                            is empty, or is a scanned image PDF
    """
    # Validate input
    if not file_bytes:
        raise PDFProcessingError("The uploaded file is empty.")

    # Check PDF magic bytes — every PDF file starts with "%PDF-"
    # This is a basic sanity check before trying to parse it
    if not file_bytes.startswith(b"%PDF"):
        raise PDFProcessingError(
            "The uploaded file does not appear to be a valid PDF. "
            "Please upload a .pdf file."
        )

    try:
        # Open the PDF from bytes
        # fitz.open() can open from a file path OR from bytes
        # stream= means "read from bytes", filetype= tells fitz the format
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        raise PDFProcessingError(f"Could not open the PDF file: {str(e)}")

    try:
        page_count = len(pdf_document)
        logger.info("Processing PDF with %s pages.", page_count)

        if page_count == 0:
            raise PDFProcessingError("The PDF file contains no pages.")

        pages = []
        total_chars = 0

        for page_index in range(page_count):
            page = pdf_document[page_index]

            # get_text() extracts all readable text from the page
            # "text" mode returns plain text with newlines between blocks
            # Other modes: "html", "dict", "rawdict", "xhtml", "xml"
            raw_text = page.get_text("text")

            # Clean up the text:
            # - Strip leading/trailing whitespace
            # - Normalize multiple blank lines to a single blank line
            cleaned_text = _clean_page_text(raw_text)

            char_count = len(cleaned_text)
            total_chars += char_count

            # page_index is 0-based internally; we store 1-based page numbers
            # because that's what users see in their PDF viewer
            pages.append({
                "page_number": page_index + 1,
                "text": cleaned_text,
                "char_count": char_count,
            })

        logger.info(
            f"Extracted {total_chars} characters from {page_count} pages "
            "from the uploaded PDF"
        )

        # Check if any text was actually extracted
        # If total_chars is near zero, the PDF is likely scanned (image-only)
        if total_chars < 50:
            raise PDFProcessingError(
                "No readable text was found in this PDF. "
                "This may be a scanned document (image-only PDF). "
                "Scanned PDFs require OCR processing, which is not yet supported. "
                "Please use a PDF with selectable text."
            )

        # Filter out pages with no meaningful content
        # (blank pages, pages with only page numbers, etc.)
        non_empty_pages = [p for p in pages if p["char_count"] > 10]

        if not non_empty_pages:
            raise PDFProcessingError(
                "All pages in this PDF appear to be empty or contain only whitespace."
            )

        logger.info(
            f"Found {len(non_empty_pages)} pages with content "
            f"({page_count - len(non_empty_pages)} empty pages skipped)"
        )

        return non_empty_pages

    finally:
        # Always close the PDF document to free memory
        # The 'finally' block runs whether we succeeded or hit an exception
        pdf_document.close()


def _clean_page_text(text: str) -> str:
    """
    Clean up extracted page text.

    PyMuPDF sometimes produces excessive whitespace or repeated blank lines.
    This function normalizes that without removing meaningful line breaks.

    Args:
        text: Raw text from page.get_text()

    Returns:
        Cleaned text string
    """
    if not text:
        return ""

    # Split into lines, strip each line, remove lines that are only whitespace
    lines = text.split("\n")
    cleaned_lines = []
    blank_count = 0  # track consecutive blank lines

    for line in lines:
        stripped = line.strip()
        if stripped:
            # Non-empty line — reset blank counter and add it
            blank_count = 0
            cleaned_lines.append(stripped)
        else:
            # Blank line — allow at most one consecutive blank line
            blank_count += 1
            if blank_count <= 1:
                cleaned_lines.append("")

    return "\n".join(cleaned_lines).strip()


def get_pdf_metadata(file_bytes: bytes) -> dict:
    """
    Extract basic metadata from a PDF without reading all text.
    Useful for quick validation before full processing.

    Returns:
        dict with: page_count, title, author, has_text
    """
    try:
        pdf_document = fitz.open(stream=file_bytes, filetype="pdf")
        metadata = pdf_document.metadata  # title, author, subject, etc.
        page_count = len(pdf_document)

        # Quick check: does the first page have any text?
        has_text = False
        if page_count > 0:
            first_page_text = pdf_document[0].get_text("text").strip()
            has_text = len(first_page_text) > 10

        pdf_document.close()

        return {
            "page_count": page_count,
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "has_text": has_text,
        }
    except Exception:
        return {"page_count": 0, "title": "", "author": "", "has_text": False}
