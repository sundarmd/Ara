"""
Vector database service using LangChain Chroma.
"""
from typing import List, Dict, Any, Optional
import asyncio
import logging
import os
import random
from chromadb.config import Settings as ChromaSettings
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
            client_settings=ChromaSettings(anonymized_telemetry=False),
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
            if c.table_artifact_path:
                metadata["table_artifact_path"] = c.table_artifact_path
            if c.table_row_start is not None:
                metadata["table_row_start"] = c.table_row_start
            if c.table_row_end is not None:
                metadata["table_row_end"] = c.table_row_end
            doc = Document(page_content=c.text, metadata=metadata, id=c.id)
            documents.append(doc)
            
        await self._run_vectorstore_operation(
            "index chunks",
            self.vectorstore.add_documents,
            documents,
        )
    
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
        filter_conditions = []
        if filter_bank:
            filter_conditions.append({"bank": filter_bank})
        if filter_asset_class:
            filter_conditions.append({"asset_class": filter_asset_class})
        if len(filter_conditions) == 1:
            where_filter = filter_conditions[0]
        elif len(filter_conditions) > 1:
            where_filter = {"$and": filter_conditions}
        else:
            where_filter = None
            
        # LangChain Chroma returns (Document, score) tuples.
        docs_and_scores = await self._run_vectorstore_operation(
            "search chunks",
            self.vectorstore.similarity_search_with_score,
            query,
            k=n_results,
            filter=where_filter,
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

    async def _run_vectorstore_operation(self, action: str, func, *args, **kwargs):
        """Run Chroma/LangChain work off-loop and retry transient provider limits."""
        loop = asyncio.get_running_loop()
        max_attempts = max(1, settings.EMBEDDING_MAX_RETRIES + 1)

        for attempt in range(max_attempts):
            try:
                return await loop.run_in_executor(
                    None,
                    lambda: func(*args, **kwargs),
                )
            except Exception as exc:
                is_last_attempt = attempt >= max_attempts - 1
                if is_last_attempt or not _is_rate_limit_error(exc):
                    raise

                delay = _retry_delay_seconds(exc, attempt)
                logger.warning(
                    "Rate limited during vector %s; retrying in %.2fs "
                    "(attempt %s/%s)",
                    action,
                    delay,
                    attempt + 1,
                    max_attempts,
                )
                await asyncio.sleep(delay)

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


def _is_rate_limit_error(exc: Exception) -> bool:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).lower()
    return "429" in message or "too many requests" in message or "rate limit" in message


def _retry_delay_seconds(exc: Exception, attempt: int) -> float:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None

    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass

    base_delay = settings.EMBEDDING_RETRY_BASE_SECONDS * (2 ** attempt)
    jitter = random.uniform(0, settings.EMBEDDING_RETRY_JITTER_SECONDS)
    return min(settings.EMBEDDING_RETRY_MAX_SECONDS, base_delay + jitter)
