from types import SimpleNamespace

import fitz
import numpy as np
import pytest
from fastapi.testclient import TestClient
from google.api_core import exceptions as google_exceptions

from app import main, rag_pipeline
from app.chunker import create_chunks
from app.config import settings
from app.document_store import document_store
from app.vector_store import build_index, search_index


@pytest.fixture(autouse=True)
def clear_document_store():
    for document in document_store.list_all():
        document_store.remove(document["document_id"])
    yield
    for document in document_store.list_all():
        document_store.remove(document["document_id"])


def make_pdf(text: str | None = "DocuMind test content") -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    if text:
        page.insert_text((72, 72), text)
    contents = pdf.tobytes()
    pdf.close()
    return contents


def make_index(text: str = "The project budget is 42 dollars."):
    chunks = create_chunks(
        [{"page_number": 7, "text": text, "char_count": len(text)}],
        document_id="test-document",
    )
    return build_index(
        chunks,
        np.array([[1.0, 0.0]], dtype=np.float32),
        document_id="test-document",
    )


def test_health_check_starts_without_loading_embedding_model(monkeypatch):
    monkeypatch.setattr(
        main,
        "embed_chunks",
        lambda chunks: pytest.fail("Health checks must not load the embedder."),
    )

    with TestClient(main.app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["generation_provider"] == "Google Gemini"
    assert response.json()["generation_model"] == settings.gemini_model


def test_pdf_upload_extracts_text_and_preserves_page_metadata(monkeypatch):
    monkeypatch.setattr(
        main,
        "embed_chunks",
        lambda chunks: np.zeros((len(chunks), 384), dtype=np.float32),
    )

    with TestClient(main.app) as client:
        response = client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "demo.pdf",
                    make_pdf(
                        "The annual result was 42. This sample text is long enough "
                        "for PDF extraction and confirms the page metadata."
                    ),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 201
    upload = response.json()
    stored = document_store.get(upload["document_id"])
    assert stored is not None
    assert stored.page_count == 1
    assert stored.doc_index.chunks[0]["page_number"] == 1
    assert "annual result" in stored.doc_index.chunks[0]["text"]


def test_upload_rejects_non_pdf_filename():
    with TestClient(main.app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("notes.txt", b"not a PDF", "text/plain")},
        )

    assert response.status_code == 400
    assert "Only PDF files" in response.json()["detail"]


def test_upload_rejects_pdf_extension_with_non_pdf_content():
    with TestClient(main.app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("fake.pdf", b"not a PDF", "application/pdf")},
        )

    assert response.status_code == 422
    assert "does not appear to be a valid PDF" in response.json()["detail"]


def test_upload_rejects_oversized_file_before_processing(monkeypatch):
    monkeypatch.setattr(settings, "max_upload_size", 1024 * 1024)

    with TestClient(main.app) as client:
        response = client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "large.pdf",
                    b"%PDF-" + b"x" * (1024 * 1024),
                    "application/pdf",
                )
            },
        )

    assert response.status_code == 413
    assert "Maximum allowed size is 1 MB" in response.json()["detail"]


def test_upload_rejects_scanned_pdf_with_helpful_message():
    with TestClient(main.app) as client:
        response = client.post(
            "/api/documents/upload",
            files={"file": ("scan.pdf", make_pdf(None), "application/pdf")},
        )

    assert response.status_code == 422
    assert "scanned document" in response.json()["detail"]


def test_only_one_document_can_be_loaded(monkeypatch):
    monkeypatch.setattr(
        main,
        "embed_chunks",
        lambda chunks: np.zeros((len(chunks), 384), dtype=np.float32),
    )

    with TestClient(main.app) as client:
        first = client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "first.pdf",
                    make_pdf(
                        "First document content. This sample contains enough text "
                        "for the PDF parser to accept it."
                    ),
                    "application/pdf",
                )
            },
        )
        second = client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "second.pdf",
                    make_pdf(
                        "Second document content. This sample contains enough text "
                        "for the PDF parser to accept it."
                    ),
                    "application/pdf",
                )
            },
        )

    assert first.status_code == 201
    assert second.status_code == 409
    assert document_store.count == 1


def test_faiss_retrieval_preserves_source_page():
    index = make_index()

    results = search_index(index, np.array([1.0, 0.0], dtype=np.float32))

    assert results[0]["page_number"] == 7
    assert "budget is 42" in results[0]["text"]


def test_answer_includes_retrieved_page_and_marks_insufficient_evidence(monkeypatch):
    index = make_index()
    monkeypatch.setattr(
        rag_pipeline,
        "embed_query",
        lambda question: np.array([1.0, 0.0], dtype=np.float32),
    )
    prompts = []

    def generate(prompt):
        prompts.append(prompt)
        return "The project budget is 42 dollars (page 7)."

    monkeypatch.setattr(rag_pipeline, "_generate_text", generate)
    answer = rag_pipeline.answer_question("What is the project budget?", index)

    assert answer["grounded"] is True
    assert answer["sources"][0]["page"] == 7
    assert "[Source 1 — Page 7]" in prompts[0]

    monkeypatch.setattr(
        rag_pipeline,
        "embed_query",
        lambda question: np.array([-1.0, 0.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "_generate_text",
        lambda prompt: pytest.fail("The LLM must not be called without relevant evidence."),
    )
    unsupported = rag_pipeline.answer_question("What is the project budget?", index)

    assert unsupported["grounded"] is False
    assert "couldn't find that information" in unsupported["answer"].lower()


def test_model_refusal_is_not_marked_as_grounded(monkeypatch):
    index = make_index()
    monkeypatch.setattr(
        rag_pipeline,
        "embed_query",
        lambda question: np.array([1.0, 0.0], dtype=np.float32),
    )
    monkeypatch.setattr(
        rag_pipeline,
        "_generate_text",
        lambda prompt: "I couldn't find that information in the uploaded document.",
    )

    answer = rag_pipeline.answer_question("Question", index)

    assert answer["grounded"] is False


def test_chat_endpoint_returns_safe_provider_error(monkeypatch):
    monkeypatch.setattr(
        main,
        "embed_chunks",
        lambda chunks: np.zeros((len(chunks), 384), dtype=np.float32),
    )

    with TestClient(main.app) as client:
        upload = client.post(
            "/api/documents/upload",
            files={
                "file": (
                    "demo.pdf",
                    make_pdf(
                        "This text is long enough to upload and supports testing "
                        "the chat API error response."
                    ),
                    "application/pdf",
                )
            },
        )
        document_id = upload.json()["document_id"]

        def fail_answer(question, doc_index):
            raise RuntimeError(
                "Failed to generate answer: Gemini API quota or credits are exhausted."
            )

        monkeypatch.setattr(
            main,
            "answer_question",
            fail_answer,
        )
        response = client.post(
            "/api/chat",
            json={"document_id": document_id, "question": "Question"},
        )

    assert upload.status_code == 201
    assert response.status_code == 502
    assert "quota or credits are exhausted" in response.json()["detail"]


def test_missing_gemini_key_has_actionable_message(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(rag_pipeline, "_gemini_model", None)

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        rag_pipeline.get_gemini_model()


def test_transient_rate_limit_retries_are_bounded(monkeypatch):
    class FakeModel:
        def __init__(self):
            self.responses = [
                google_exceptions.TooManyRequests("rate limit"),
                SimpleNamespace(candidates=[object()], text="Recovered answer"),
            ]

        def generate_content(self, prompt):
            result = self.responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

    sleeps = []
    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: FakeModel())
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    answer = rag_pipeline._call_gemini("Question")

    assert answer == "Recovered answer"
    assert sleeps == [1]


def test_repeated_rate_limit_stops_after_two_retries(monkeypatch):
    class FakeModel:
        def __init__(self):
            self.calls = 0

        def generate_content(self, prompt):
            self.calls += 1
            raise google_exceptions.TooManyRequests("rate limit")

    model = FakeModel()
    sleeps = []
    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: model)
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="temporarily rate-limiting"):
        rag_pipeline._call_gemini("Question")

    assert model.calls == 3
    assert sleeps == [1, 2]


@pytest.mark.parametrize(
    "provider_error",
    [
        google_exceptions.ServiceUnavailable("service unavailable"),
        ConnectionError("network unavailable"),
    ],
)
def test_transient_provider_and_network_errors_are_sanitized_and_bounded(
    monkeypatch, provider_error
):
    class FakeModel:
        def __init__(self):
            self.calls = 0

        def generate_content(self, prompt):
            self.calls += 1
            raise provider_error

    model = FakeModel()
    sleeps = []
    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: model)
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError) as error:
        rag_pipeline._call_gemini("Question")

    assert model.calls == 3
    assert sleeps == [1, 2]
    assert "unavailable" in str(error.value).lower() or "could not reach" in str(error.value).lower()
    assert str(provider_error) not in str(error.value)


def test_exhausted_quota_is_not_retried_or_exposed_raw(monkeypatch):
    class FakeModel:
        def generate_content(self, prompt):
            raise google_exceptions.ResourceExhausted("quota exceeded: sensitive detail")

    sleeps = []
    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: FakeModel())
    monkeypatch.setattr(rag_pipeline.time, "sleep", sleeps.append)

    with pytest.raises(RuntimeError, match="quota or credits are exhausted") as error:
        rag_pipeline._call_gemini("Question")

    assert sleeps == []
    assert "sensitive detail" not in str(error.value)


def test_invalid_gemini_key_error_does_not_expose_raw_details(monkeypatch):
    class FakeModel:
        def generate_content(self, prompt):
            raise google_exceptions.Unauthenticated("invalid api key: secret-value")

    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: FakeModel())

    with pytest.raises(RuntimeError, match="Gemini rejected the API key") as error:
        rag_pipeline._call_gemini("Question")

    assert "secret-value" not in str(error.value)


def test_unavailable_gemini_model_has_clear_message(monkeypatch):
    class FakeModel:
        def generate_content(self, prompt):
            raise google_exceptions.NotFound("model not found: internal details")

    monkeypatch.setattr(rag_pipeline, "get_gemini_model", lambda: FakeModel())

    with pytest.raises(RuntimeError, match="Gemini model .* is unavailable") as error:
        rag_pipeline._call_gemini("Question")

    assert "internal details" not in str(error.value)
