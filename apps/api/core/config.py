from pydantic_settings import BaseSettings
from pydantic import model_validator


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "AI Knowledge Graph Builder"

    # Supabase
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    SUPABASE_JWKS_URL: str = ""

    # Mock auth for development (bypasses Supabase)
    MOCK_AUTH: bool = False

    # Database — set in .env for production; dev always uses SQLite
    DATABASE_URL: str = "sqlite+aiosqlite:///./akgb.db"

    @model_validator(mode="after")
    def _force_sqlite_in_dev(self):
        if self.ENVIRONMENT == "development":
            self.DATABASE_URL = "sqlite+aiosqlite:///./akgb.db"
        return self

    @model_validator(mode="after")
    def _reject_mock_in_prod(self):
        if self.ENVIRONMENT == "production" and self.MOCK_AUTH:
            raise ValueError(
                "MOCK_AUTH=true is not allowed in production. "
                "Set MOCK_AUTH=false and configure real Supabase credentials."
            )
        return self

    # ChromaDB
    CHROMA_PATH: str = "./chroma_data"

    # Text Generation (OpenAI-compatible)
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "qwen3:4b-instruct"

    # Embeddings (OpenAI-compatible)
    EMBEDDING_API_KEY: str = ""
    EMBEDDING_BASE_URL: str = "http://localhost:11434/v1"
    EMBEDDING_MODEL: str = "qwen3-embedding:4b"

    # Google Meet Bot agent
    MEET_EMAIL: str = ""
    MEET_PASSWORD: str = ""
    MEET_CHROME_DRIVER: str = ""  # path to chromedriver if not on PATH
    MEET_CHROME_PROFILE: str = ""  # persistent Chrome profile dir (recommended: log in once by hand)
    MEET_AUDIO_DIR: str = "./meet_recordings"
    MEET_SAMPLE_RATE: int = 44100
    MEET_MAX_AUDIO_BYTES: int = 20 * 1024 * 1024

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
