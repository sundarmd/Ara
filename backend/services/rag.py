"""
RAG Service.

Handles semantic search operations on the vector store.
Separated from agent_orchestrator to avoid circular imports.
"""
import logging
from typing import Optional, List, Dict, Any

from services.database import ResearchVectorStore, get_vector_store
from services.embeddings import get_embedding_client

logger = logging.getLogger(__name__)



async def search_documents(
    query: str,
    n_results: int = 5,
    filter_bank: Optional[str] = None,
    filter_asset_class: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search indexed documents using semantic similarity.
    
    Args:
        query: Natural language query
        n_results: Number of results to return
        filter_bank: Optional filter by bank
        filter_asset_class: Optional filter by asset class
        
    Returns:
        List of matching chunks with metadata
    """
    # Search vector store
    vector_store = get_vector_store()
    
    # LangChain vector store handles embedding generation
    results = await vector_store.search(
        query=query,
        n_results=n_results,
        filter_bank=filter_bank,
        filter_asset_class=filter_asset_class,
    )
    
    return results
