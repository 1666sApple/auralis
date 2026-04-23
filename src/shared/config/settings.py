"""Application configuration settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str
    APP_VERSION: str
    DEBUG: bool

    # AWS Credentials
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_S3_BUCKET: Optional[str] = None
    AWS_REGION: str
    AWS_REGION_IMAGE: str
    AWS_REGION_EMBEDDING: Optional[str] = None

    # Bedrock API Configuration
    BEDROCK_API: Optional[str] = None
    BEDROCK_API_NAME: Optional[str] = None

    # Google Gemini API
    GOOGLE_API_KEY: Optional[str] = None

    # Bedrock Models
    EMBEDDING_MODEL_ID: str
    LLM_SONNET_MODEL_ID: str
    LLM_HAIKU_MODEL_ID: str
    LLM_MODEL_ID: str
    LLM_TITLE_MODEL_ID: str
    LLM_ENRICHMENT_MODEL_ID: str
    MEM0_LLM_MODEL: str
    IMAGE_MODEL_ID: str

    # Model Parameters
    LLM_TEMPERATURE: float
    LLM_MAX_TOKENS: int
    LLM_THINKING_BUDGET: int = 2000

    # Qdrant Vector Store Settings
    QDRANT_MODE: str
    QDRANT_STORAGE_PATH: str
    QDRANT_SERVER_URL: str

    # Legacy paths (for migration reference)
    SQLITE_DB_PATH: str

    # HR Database Settings
    HR_DB_CONNECTION_STRING: str
    HR_DB_TYPE: str

    # Document Processing
    MAX_CHUNK_SIZE: int
    EMBEDDING_BATCH_SIZE: int
    EMBEDDING_DIMENSION: int

    # Retrieval Settings
    DEFAULT_TOP_K: int
    DEFAULT_SCORE_THRESHOLD: Optional[float] = None
    RERANKER_MODEL_ID: str
    CORRECTIVE_SKIP_THRESHOLD: float

    # Performance Optimization Flags
    ENABLE_SCOPE_VALIDATION: bool
    
    # OCR Optimization
    OCR_ENABLE_MKLDNN: bool = False
    OCR_CPU_THREADS: int = 10
    OCR_MKLDNN_CACHE_CAPACITY: int = 10

    # Document Generation Settings
    DOC_TEMPLATE_PATH: str
    DOC_OUTPUT_DIR: str
    DOC_GENERATION_TIMEOUT: int
    DOC_LLM_MAX_RETRIES: int
    DOC_LLM_RETRY_BASE_DELAY: float

    # Search API Keys
    TAVILY_API_KEY: Optional[str] = None
    LANGSEARCH_API_KEY: Optional[str] = None

    # API Settings
    API_PREFIX: str
    CORS_ORIGINS: list

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


# Global settings instance
settings = Settings()
