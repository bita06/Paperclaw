"""
Application Configuration
"""
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # === Application ===
    APP_ENV: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    LOG_LEVEL: str = Field(default="INFO")
    PROJECT_NAME: str = Field(default="PaperClaw")
    PROJECT_VERSION: str = Field(default="0.1.0")
    API_V1_STR: str = Field(default="/api/v1")

    # === Server ===
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)

    # === Storage ===
    STORAGE_ROOT: str = Field(default=str(REPO_ROOT / 'paper_uploads'))
    BUILTIN_LIBRARY_ROOT: str = Field(default=str(REPO_ROOT / 'data' / 'builtin_library'))

    # === Database ===
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://paperclaw_user:password@localhost:5432/paperclaw_db"
    )
    DB_ECHO: bool = Field(default=False)
    DB_POOL_SIZE: int = Field(default=20)
    DB_MAX_OVERFLOW: int = Field(default=10)

    # === Vector Database (Pinecone) ===
    PINECONE_API_KEY: str = Field(default="")
    PINECONE_INDEX_NAME: str = Field(default="paperclaw-index")
    PINECONE_ENVIRONMENT: str = Field(default="us-west1-gcp")
    EMBEDDING_DIMENSION: int = Field(default=1536)
    EMBEDDING_PROVIDER: str = Field(default="minimax")

    # === LLM (OpenAI legacy) ===
    OPENAI_API_KEY: str = Field(default="")
    LLM_MODEL: str = Field(default="gpt-3.5-turbo")
    LLM_EMBEDDING_MODEL: str = Field(default="text-embedding-ada-002")
    MAX_TOKENS: int = Field(default=2048)
    TEMPERATURE: float = Field(default=0.7)

    # === LLM (MiniMax parser / embeddings) ===
    MINIMAX_API_KEY: str = Field(default="")
    MINIMAX_BASE_URL: str = Field(default="https://api.minimaxi.com/v1/text/chatcompletion_v2")
    MINIMAX_MODEL: str = Field(default="MiniMax-M2.5")
    MINIMAX_EMBEDDING_URL: str = Field(default="https://api.minimaxi.com/v1/embeddings")
    MINIMAX_EMBEDDING_MODEL: str = Field(default="embo-01")
    MINIMAX_TIMEOUT_SECONDS: int = Field(default=60)

    # === Web of Science ===
    WOS_API_KEY: str = Field(default="")
    WOS_BASE_URL: str = Field(default="https://api.clarivate.com/apis/wos-starter/v1")
    WOS_API_URL: str = Field(default="https://api.clarivate.com/apis/wos-starter/v1")
    WOS_TIMEOUT_SECONDS: int = Field(default=15)

    # === Web Search (Tavily) ===
    TAVILY_API_KEY: str = Field(default="")
    TAVILY_SEARCH_URL: str = Field(default="https://api.tavily.com/search")

    # === Redis Cache ===
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CACHE_TTL: int = Field(default=3600)

    # === Zep Memory ===
    ENABLE_ZEP_MEMORY: bool = Field(default=False)
    ZEP_API_KEY: str = Field(default="")
    ZEP_API_BASE_URL: str = Field(default="https://api.getzep.com/api/v2")
    ZEP_TIMEOUT_SECONDS: int = Field(default=30)
    ZEP_LASTN_MESSAGES: int = Field(default=6)

    # === Authentication ===
    SECRET_KEY: str = Field(default="your-secret-key-change-in-production")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    BOOTSTRAP_DEVELOPER_ADMIN_EMAIL: str = Field(default="")
    BOOTSTRAP_DEVELOPER_ADMIN_PASSWORD: str = Field(default="")
    BOOTSTRAP_DEVELOPER_ADMIN_NAME: str = Field(default="PaperClaw Developer Admin")
    BOOTSTRAP_DEVELOPER_ADMIN_DEPARTMENT: str = Field(default="PaperClaw")

    # === CORS ===
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000", "http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # === Feature Flags ===
    ENABLE_VECTOR_SEARCH: bool = Field(default=True)
    ENABLE_LLM_FEATURES: bool = Field(default=True)
    ENABLE_PDF_PROCESSING: bool = Field(default=True)
    ENABLE_WEB_SEARCH: bool = Field(default=True)
    ENABLE_WOS_SEARCH: bool = Field(default=True)

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "on", "debug", "development"}:
                return True
            if lowered in {"false", "0", "no", "off", "release", "prod", "production"}:
                return False
        return value

    class Config:
        env_file = str(BACKEND_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
