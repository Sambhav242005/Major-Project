from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator

# Supported values for EMBEDDING_PROVIDER.
#   openai -> any OpenAI-compatible /embeddings endpoint (Ollama, Groq, OpenAI)
#   gemini -> Google Gemini native :batchEmbedContents endpoint
EMBEDDING_PROVIDERS = frozenset({"openai", "gemini", "local", "ollama"})


class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
    )
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "AI Knowledge Graph Builder"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWKS_URL: str = ""
    AUTH_PROVIDER: str = "supabase"
    LOCAL_AUTH_SECRET: str = ""
    AUTH_PROXY_SECRET: str = ""
    LOCAL_AUTH_TOKEN_TTL_SECONDS: int = 3600
    LOCAL_AUTH_ALLOW_SIGNUP: bool = False

    # Mock auth for development (bypasses Supabase)
    MOCK_AUTH: bool = False

    # Database — set in .env for production; dev always uses SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./akgb.db"

    @model_validator(mode="after")
    def _force_sqlite_in_dev(self):
        # Respect explicit postgres DATABASE_URL in development (e.g. docker-compose).
        # Only force SQLite when no postgres URL was provided.
        if self.ENVIRONMENT == "development":
            low = self.DATABASE_URL.lower()
            if "postgres" not in low and "postgresql" not in low:
                self.DATABASE_URL = "sqlite+aiosqlite:///./akgb.db"
        return self

    @model_validator(mode="after")
    def _reject_mock_in_prod(self):
        if self.ENVIRONMENT == "production" and self.MOCK_AUTH:
            raise ValueError(
                "MOCK_AUTH=true is not allowed in production. "
                "Set MOCK_AUTH=false and configure real Supabase credentials."
            )
        self.AUTH_PROVIDER = self.AUTH_PROVIDER.strip().lower()
        if self.AUTH_PROVIDER not in {"supabase", "local"}:
            raise ValueError("AUTH_PROVIDER must be supabase or local")
        if self.AUTH_PROVIDER == "local" and len(self.LOCAL_AUTH_SECRET) < 32:
            raise ValueError("Local authentication requires LOCAL_AUTH_SECRET of at least 32 characters")
        if self.AUTH_PROXY_SECRET and len(self.AUTH_PROXY_SECRET) < 32:
            raise ValueError("AUTH_PROXY_SECRET must contain at least 32 characters when configured")
        if not 60 <= self.LOCAL_AUTH_TOKEN_TTL_SECONDS <= 86400:
            raise ValueError("LOCAL_AUTH_TOKEN_TTL_SECONDS must be between 60 and 86400")
        return self

    # ChromaDB
    CHROMA_PATH: str = "./chroma_data"

    # Text Generation (OpenAI-compatible)
    LLM_PROVIDER: str = "openai"
    CHATGPT_CREDENTIALS_PATH: str = ""
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "qwen3:4b-instruct"

    LLM_CHAT_MODEL: str = "qwen/qwen3.8-27b"
    LLM_EXTRACT_MODEL: str = "qwen/qwen3.8-27b"

    # Embeddings
    # EMBEDDING_PROVIDER=openai  -> any OpenAI-compatible /embeddings endpoint
    #                               (Ollama, Groq, OpenAI, Gemini's compat layer)
    # EMBEDDING_PROVIDER=gemini  -> Google Gemini native :batchEmbedContents
    EMBEDDING_PROVIDER: str = "openai"
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_MODEL: str = "qwen3-embedding:4b"
    # Optional output dimensionality. Only send it when the provider/model
    # supports it (Gemini: 768/1536/3072 via Matryoshka truncation).
    EMBEDDING_OUTPUT_DIM: int | None = None
    EMBEDDING_BATCH_SIZE: int = 100
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Opt-in knowledge-source media processing; services/models are operator-managed.
    MEDIA_INGESTION_ENABLED: bool = False
    WHISPER_BASE_URL: str = ""
    WHISPER_MODEL: str = "whisper-1"
    WHISPER_API_KEY: str = ""
    VLM_MODEL: str = ""
    MEDIA_MAX_DURATION_SECONDS: int = 600
    MEDIA_MAX_FRAMES: int = 12
    MEDIA_PROCESS_TIMEOUT_SECONDS: int = 120

    # Gemini native provider (used when EMBEDDING_PROVIDER=gemini).
    # GEMINI_API_KEY falls back to EMBEDDING_API_KEY when empty.
    GEMINI_API_KEY: str = ""
    GEMINI_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"

    # Google Meet Bot agent
    MEET_EMAIL: str = ""
    MEET_PASSWORD: str = ""
    MEET_CHROME_DRIVER: str = ""  # path to chromedriver if not on PATH
    MEET_CHROME_PROFILE: str = ""  # persistent Chrome profile dir (recommended: log in once by hand)
    MEET_AUDIO_DIR: str = "./meet_recordings"
    MEET_SAMPLE_RATE: int = 44100
    MEET_MAX_AUDIO_BYTES: int = 20 * 1024 * 1024

    # GitHub repository ingestion (Phase 1: public repositories)
    # Only https://github.com is accepted as the repository web host and only
    # api.github.com as the API host; redirects to other hosts are blocked.
    GITHUB_API_BASE_URL: str = "https://api.github.com"
    GITHUB_IMPORT_MAX_TOTAL_BYTES: int = 50 * 1024 * 1024
    GITHUB_IMPORT_MAX_FILES: int = 2000
    GITHUB_IMPORT_MAX_FILE_BYTES: int = 2 * 1024 * 1024

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    @model_validator(mode="after")
    def _validate_embedding_settings(self):
        provider = self.EMBEDDING_PROVIDER.strip().lower()
        if provider not in EMBEDDING_PROVIDERS:
            raise ValueError(
                f"EMBEDDING_PROVIDER must be one of {sorted(EMBEDDING_PROVIDERS)}, "
                f"got {self.EMBEDDING_PROVIDER!r}"
            )
        self.EMBEDDING_PROVIDER = provider

        self.LLM_PROVIDER = self.LLM_PROVIDER.strip().lower()
        if self.LLM_PROVIDER not in {"openai", "chatgpt"}:
            raise ValueError("LLM_PROVIDER must be openai or chatgpt")
        if provider == "local":
            if self.EMBEDDING_MODEL != "all-MiniLM-L6-v2":
                raise ValueError("Local embeddings require EMBEDDING_MODEL=all-MiniLM-L6-v2")
            if self.EMBEDDING_OUTPUT_DIM not in (None, 384):
                raise ValueError("Local MiniLM embeddings have 384 dimensions")

        if self.EMBEDDING_BATCH_SIZE < 1:
            raise ValueError("EMBEDDING_BATCH_SIZE must be >= 1")
        if not 1 <= self.MEDIA_MAX_DURATION_SECONDS <= 3600:
            raise ValueError("MEDIA_MAX_DURATION_SECONDS must be between 1 and 3600")
        if not 1 <= self.MEDIA_MAX_FRAMES <= 60 or not 1 <= self.MEDIA_PROCESS_TIMEOUT_SECONDS <= 600:
            raise ValueError("Media frame/timeout limits are outside the supported range")
        if provider == "ollama" and self.EMBEDDING_MODEL.startswith("embeddinggemma-2"):
            if self.EMBEDDING_OUTPUT_DIM not in (None, 128, 256, 512, 768):
                raise ValueError("EmbeddingGemma 2 dimensions must be 128, 256, 512 or 768")

        if provider == "gemini" and not (self.GEMINI_API_KEY or self.EMBEDDING_API_KEY):
            raise ValueError(
                "EMBEDDING_PROVIDER=gemini requires GEMINI_API_KEY "
                "(or EMBEDDING_API_KEY as a fallback)."
            )
        return self




settings = Settings()
