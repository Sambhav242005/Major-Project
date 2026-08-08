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

    # ChromaDB
    CHROMA_PATH: str = "./chroma_data"

    # LLM
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1"
    LLM_PROVIDER: str = "openai"  # "openai" or "ollama"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
