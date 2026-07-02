import json
import os
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Mistral API settings
    MISTRAL_API_KEY: Optional[str] = None
    MISTRAL_OCR_ENDPOINT: str = "https://api.mistral.ai/v1/ocr"
    MISTRAL_CHAT_ENDPOINT: str = "https://api.mistral.ai/v1/chat/completions"
    MISTRAL_CHAT_MODEL: str = "mistral-large-latest"
    EMBEDDING_MODEL_NAME: str = "mistral-embed"
    
    # Web Search
    TAVILY_API_KEY: Optional[str] = None
    
    # Vector database settings
    VECTOR_DB_DIR: str = "./data/vector_store"
    
    # Data storage settings
    DATA_ROOT: str = "./data"
    DATA_DIR: str = "./data/reports"  # Legacy report/PDF directory setting
    REPORTS_DIR: Optional[str] = None
    DOCUMENTS_DB_PATH: Optional[str] = None
    RECOMMENDATIONS_DB_PATH: Optional[str] = None
    IMAGES_DIR: str = "./data/images"
    PROMPTS_DIR: str = "./prompts"
    RECOMMENDATIONS_PATH: str = "./data/recommendations.json"
    MAX_UPLOAD_MB: float = 50.0
    MAX_UPLOAD_FILES: int = 5

    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ALLOWED_ORIGINS: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOWED_METHODS: List[str] = Field(
        default_factory=lambda: ["GET", "POST", "DELETE", "OPTIONS"]
    )
    CORS_ALLOWED_HEADERS: List[str] = Field(
        default_factory=lambda: ["Content-Type", "Authorization"]
    )
    REQUIRE_API_KEY: bool = False
    API_KEY: Optional[str] = None
    API_KEY_HEADER_NAME: str = "X-API-Key"

    @field_validator(
        "CORS_ALLOWED_ORIGINS",
        "CORS_ALLOWED_METHODS",
        "CORS_ALLOWED_HEADERS",
        mode="before",
    )
    @classmethod
    def parse_csv_list(cls, value):
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value
    
    @property
    def API_BASE_URL(self) -> str:
        """Construct base URL for deep links."""
        host = self.API_HOST if self.API_HOST != "0.0.0.0" else "localhost"
        return f"http://{host}:{self.API_PORT}"

    @property
    def reports_dir(self) -> str:
        """Directory where uploaded source PDFs are stored."""
        return self.REPORTS_DIR or self.DATA_DIR

    @property
    def documents_db_path(self) -> str:
        """SQLite path for document metadata."""
        return self.DOCUMENTS_DB_PATH or os.path.join(self.DATA_ROOT, "documents.db")

    @property
    def recommendations_db_path(self) -> str:
        """SQLite path for recommendations and analyst intelligence."""
        return self.RECOMMENDATIONS_DB_PATH or os.path.join(
            self.DATA_ROOT,
            "recommendations.db",
        )
    
    # RAG settings
    RAG_SEARCH_RESULTS: int = 8
    RAG_CONTEXT_RECOMMENDATIONS: int = 15
    RAG_RESPONSE_RECOMMENDATIONS: int = 10
    
    # Timeout settings (seconds)
    TIMEOUT_CHAT: float = 90.0
    TIMEOUT_EMBEDDING: float = 60.0
    TIMEOUT_OCR: float = 120.0
    
    # Streaming settings
    STREAM_CHUNK_SIZE: int = 5
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def ensure_directories():
    """Create required directories if they don't exist."""
    os.makedirs(settings.DATA_ROOT, exist_ok=True)
    os.makedirs(settings.reports_dir, exist_ok=True)
    os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
    os.makedirs(settings.IMAGES_DIR, exist_ok=True)
    # Ensure parent directory for recommendations file exists
    os.makedirs(os.path.dirname(settings.RECOMMENDATIONS_PATH), exist_ok=True)
    for db_path in (settings.documents_db_path, settings.recommendations_db_path):
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
