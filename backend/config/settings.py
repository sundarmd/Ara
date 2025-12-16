import os
from pydantic_settings import BaseSettings
from typing import Optional


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
    DATA_DIR: str = "./data/reports"
    IMAGES_DIR: str = "./data/images"
    PROMPTS_DIR: str = "./prompts"
    RECOMMENDATIONS_PATH: str = "./data/recommendations.json"

    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    
    @property
    def API_BASE_URL(self) -> str:
        """Construct base URL for deep links."""
        host = self.API_HOST if self.API_HOST != "0.0.0.0" else "localhost"
        return f"http://{host}:{self.API_PORT}"
    
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
    os.makedirs(settings.DATA_DIR, exist_ok=True)
    os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
    os.makedirs(settings.IMAGES_DIR, exist_ok=True)
    # Ensure parent directory for recommendations file exists
    os.makedirs(os.path.dirname(settings.RECOMMENDATIONS_PATH), exist_ok=True)
