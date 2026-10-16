"""
config.py — Application Configuration

This file reads settings from environment variables (and the .env file).

Why do this?
- API keys and secrets must NEVER be hardcoded in Python files.
- If you hardcode them and push to GitHub, they are exposed permanently.
- Instead, we store them in a .env file that is excluded from Git.
- pydantic-settings reads that file and gives us a clean Python object.

How to use it anywhere in the app:
    from app.config import settings
    # Read secret settings only in backend code; never return them to clients.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Each attribute here corresponds to a variable in your .env file.
    If a required variable is missing, the app will fail at startup with
    a clear error — better than failing silently mid-request.
    """

    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # Maximum file upload size in bytes (default: 10 MB)
    # 10 * 1024 * 1024 = 10,485,760 bytes
    max_upload_size: int = 10 * 1024 * 1024

    # The UI handles one active document; enforce the same memory limit in the API.
    max_loaded_documents: int = 1

    # Retrieve several passages so answers can use evidence across the PDF.
    top_k_chunks: int = 5

    # Minimum similarity score (0.0 to 1.0) for a chunk to be considered relevant
    # Chunks scoring below this are ignored — helps prevent irrelevant answers
    # 0.2 is a good starting point — low enough to catch paraphrased questions,
    # high enough to filter truly unrelated content
    relevance_threshold: float = 0.2

    # Chunk size in characters — how long each text piece should be
    chunk_size: int = 800

    # Chunk overlap in characters — how much adjacent chunks share
    # Overlap preserves context that would otherwise be cut at a boundary
    chunk_overlap: int = 150

    # Embedding model name from HuggingFace Hub
    # all-MiniLM-L6-v2 is small (80MB), fast, and accurate enough for this project
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Suppress TensorFlow — we use PyTorch only
    # These prevent the transformers library from trying to import TF
    use_tf: str = "0"
    transformers_no_tf: str = "1"
    tf_cpp_min_log_level: str = "3"
    tf_enable_onednn_opts: str = "0"

    # Tell pydantic-settings to look for a .env file in the backend directory
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # Don't crash if .env file doesn't exist — just use defaults
        extra="ignore",
    )


# Create a single instance that the rest of the app imports.
# This is called the "singleton pattern" — one shared object, loaded once.
settings = Settings()
