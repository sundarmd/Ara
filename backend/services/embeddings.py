"""
Embedding client using LangChain (OpenAI Adapter for Mistral).
"""
from langchain_openai import OpenAIEmbeddings
from config.settings import settings

def get_embedding_client() -> OpenAIEmbeddings:
    """
    Get the LangChain embedding client configured for Mistral.
    Mistral's embedding API is compatible with OpenAI's format.
    """
    if not settings.MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is required")
        
    return OpenAIEmbeddings(
        api_key=settings.MISTRAL_API_KEY,
        base_url="https://api.mistral.ai/v1",
        model=settings.EMBEDDING_MODEL_NAME,
        check_embedding_ctx_length=False 
    )
