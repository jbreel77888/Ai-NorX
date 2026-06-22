"""
Ai NorX - Backend Application Configuration
Pydantic Settings for environment variables
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ━━━ Application ━━━
    PROJECT_NAME: str = "Ai NorX"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"
    SUPPORT_EMAIL: str = "jbrel77189@gmail.com"

    # ━━━ Database ━━━
    DATABASE_URL: str
    DATABASE_URL_SYNC: Optional[str] = None

    # ━━━ Redis (Upstash) ━━━
    UPSTASH_REDIS_REST_URL: str
    UPSTASH_REDIS_REST_TOKEN: str
    REDIS_URL: Optional[str] = None

    # ━━━ Clerk Auth ━━━
    CLERK_SECRET_KEY: str
    NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: Optional[str] = None

    # ━━━ Cloudflare R2 ━━━
    R2_ACCOUNT_ID: str
    R2_ACCESS_KEY_ID: str
    R2_SECRET_ACCESS_KEY: str
    R2_BUCKET_NAME: str = "ainorx"
    R2_ENDPOINT: str
    R2_PUBLIC_URL: Optional[str] = None

    # ━━━ Sentry ━━━
    SENTRY_DSN_BACKEND: Optional[str] = None

    # ━━━ LLM Providers ━━━
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_API_KEY: str

    OPENCODE_BASE_URL: str = "https://opencode.ai/zen/v1"
    OPENCODE_API_KEY: str

    HUGGINGFACE_TOKEN: Optional[str] = None
    HUGGINGFACE_EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # ━━━ Web Search ━━━
    SERPER_API_KEY: str

    # ━━━ Security ━━━
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:3000"

    # ━━━ URLs ━━━
    NEXT_PUBLIC_APP_URL: str = "http://localhost:3000"
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000"
    API_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    # ━━━ Feature Flags ━━━
    ENABLE_RAG: bool = True
    ENABLE_TOOLS: bool = True
    ENABLE_MEMORY: bool = True
    ENABLE_CODE_INTERPRETER: bool = False
    ENABLE_DEEP_RESEARCH: bool = False

    @field_validator("CORS_ORIGINS")
    @classmethod
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def async_database_url(self) -> str:
        """Ensure DATABASE_URL uses asyncpg driver."""
        url = self.DATABASE_URL
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def sync_database_url(self) -> str:
        """Get sync DATABASE_URL for Alembic."""
        if self.DATABASE_URL_SYNC:
            return self.DATABASE_URL_SYNC
        url = self.DATABASE_URL
        if "asyncpg" in url:
            return url.replace("postgresql+asyncpg://", "postgresql://", 1)
        return url


# Load from .env.local in development (if exists)
# In production (Railway/Vercel), env vars come from the platform
_env_file = os.environ.get("ENV_FILE", ".env")
if os.path.exists(_env_file) and not os.environ.get("DATABASE_URL"):
    # Load local .env file into environment
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
