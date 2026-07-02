"""
Vector database service using LangChain Chroma.
"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
import os
from langchain_chroma import Chroma
from langchain_core.documents import Document

from config.settings import settings

logger = logging.getLogger(__name__)
from services.embeddings import get_embedding_client
from models.schemas import Chunk


class ResearchVectorStore:
    """
    LangChain-based Vector store wrapper.
    """
    
    def __init__(self):
        """Initialize the LangChain Chroma vector store."""
        os.makedirs(settings.VECTOR_DB_DIR, exist_ok=True)
        
        self.embedding_function = get_embedding_client()
        
        self.vectorstore = Chroma(
            collection_name="research_chunks",
            embedding_function=self.embedding_function,
            persist_directory=settings.VECTOR_DB_DIR,
            collection_metadata={"description": "Sell-side research report chunks"}
        )
    
    async def index_chunks(self, chunks: List[Chunk]):
        """
        Store chunks in Chroma using LangChain documents.
        
        Args:
            chunks: List of Chunk objects to store
        """
        if not chunks:
            return
        
        documents = []
        for c in chunks:
            metadata = {
                "doc_id": c.doc_id,
                "bank": c.bank,
                "asset_class": c.asset_class,
                "report_date": c.report_date,
                "page_start": c.page_start,
                "page_end": c.page_end,
                "section": c.section or "",
                "segment_types": ",".join(c.segment_types),
            }
            doc = Document(page_content=c.text, metadata=metadata, id=c.id)
            documents.append(doc)
            
        # Add to vectorstore (run in thread pool to avoid blocking async loop)
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.vectorstore.add_documents, documents)
    
    async def search(
        self,
        query: str,
        n_results: int = 5,
        filter_bank: Optional[str] = None,
        filter_asset_class: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar chunks using semantic search.
        
        Args:
            query: Natural language query
            n_results: Number of results
            filter_bank: Filter by bank
            filter_asset_class: Filter by asset class
            
        Returns:
            List of matching chunks with metadata
        """
        where_filter = {}
        if filter_bank:
            where_filter["bank"] = filter_bank
        if filter_asset_class:
            where_filter["asset_class"] = filter_asset_class
            
        # LangChain Chroma returns (Document, score) tuples.
        loop = asyncio.get_running_loop()
        docs_and_scores = await loop.run_in_executor(
            None,
            lambda: self.vectorstore.similarity_search_with_score(
                query,
                k=n_results,
                filter=where_filter if where_filter else None,
            ),
        )
        
        formatted_results = []
        for doc, score in docs_and_scores:
            formatted_results.append({
                "id": doc.id,
                "text": doc.page_content,
                "metadata": doc.metadata,
                "distance": score, # Chroma returns distance (lower is better)
            })
            
        return formatted_results
    
    def as_retriever(self, **kwargs):
        """Return as a standard LangChain retriever."""
        return self.vectorstore.as_retriever(**kwargs)

    def get_collection_stats(self) -> Dict[str, Any]:
        """Return lightweight stats for the persisted Chroma collection."""
        collection = getattr(self.vectorstore, "_collection", None)
        document_count = collection.count() if collection is not None else 0

        return {
            "collection_name": "research_chunks",
            "document_count": document_count,
            "persist_directory": settings.VECTOR_DB_DIR,
        }
        
    def delete_document(self, doc_id: str) -> int:
        """
        Delete all chunks associated with a doc_id.
        """
        where_filter = {"doc_id": doc_id}
        matching = self.vectorstore.get(where=where_filter)
        ids = list(matching.get("ids") or [])
        if not ids:
            return 0

        self.vectorstore.delete(ids=ids)

        remaining = self.vectorstore.get(where=where_filter)
        remaining_ids = list(remaining.get("ids") or [])
        if remaining_ids:
            raise RuntimeError(
                f"Vector deletion verification failed for doc_id={doc_id}; "
                f"{len(remaining_ids)} chunks remain"
            )

        logger.info("Deleted %s vector chunks for doc_id=%s", len(ids), doc_id)
        return len(ids)

# Singleton instance
_vector_store: Optional[ResearchVectorStore] = None


def get_vector_store() -> ResearchVectorStore:
    """Get or create the vector store singleton."""
    global _vector_store
    if _vector_store is None:
        _vector_store = ResearchVectorStore()
    return _vector_store
