"""
Ingestion service for PDF document processing pipeline.

This module owns all indexing logic:
- PDF parsing (Mistral OCR)
- Chunking (Smart Segment-Aware)
- Embedding (Managed by Vector Store)
- Vector store indexing
- Recommendation extraction (Mistral Chat)
"""
import logging
import os
import shutil
from typing import Optional, List, Callable, Awaitable

from models.schemas import Chunk, Recommendation
from config.settings import settings
from services.document_reader import parse_pdf_to_segments
from services.chunker import build_chunks
from services.database import ResearchVectorStore, get_vector_store
from services.errors import format_ingestion_error
from services.recommendations import (
    extract_recommendations_with_mistral,
    get_recommendation_store,
)
from services.metadata_extractor import extract_metadata_from_content

logger = logging.getLogger(__name__)

# Progress callback type
ProgressCallback = Callable[[str, int, str], Awaitable[None]]


def _cleanup_failed_ingestion(
    doc_id: str,
    file_path: str,
    vector_store: Optional[ResearchVectorStore] = None,
) -> dict:
    """Best-effort cleanup for artifacts created before ingestion failed."""
    cleanup = {
        "vectors_deleted": False,
        "recommendations_deleted": 0,
        "images_deleted": False,
        "pdf_deleted": False,
    }

    if vector_store is not None:
        try:
            vector_store.delete_document(doc_id)
            cleanup["vectors_deleted"] = True
        except Exception as cleanup_error:
            logger.warning(
                "Failed to cleanup vectors for doc_id=%s: %s",
                doc_id,
                cleanup_error,
                exc_info=True,
            )

    try:
        cleanup["recommendations_deleted"] = (
            get_recommendation_store().delete_by_doc_id(doc_id)
        )
    except Exception as cleanup_error:
        logger.warning(
            "Failed to cleanup recommendations for doc_id=%s: %s",
            doc_id,
            cleanup_error,
            exc_info=True,
        )

    images_dir = os.path.join(settings.IMAGES_DIR, doc_id)
    if os.path.exists(images_dir):
        try:
            shutil.rmtree(images_dir)
            cleanup["images_deleted"] = True
        except Exception as cleanup_error:
            logger.warning(
                "Failed to cleanup images for doc_id=%s: %s",
                doc_id,
                cleanup_error,
                exc_info=True,
            )

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
            cleanup["pdf_deleted"] = True
        except Exception as cleanup_error:
            logger.warning(
                "Failed to cleanup PDF for doc_id=%s: %s",
                doc_id,
                cleanup_error,
                exc_info=True,
            )

    return cleanup


async def ingest_pdf(
    doc_id: str,
    file_path: str,
    bank: str = None,
    asset_class: str = None,
    report_date: str = None,
    title: str = None,
    on_progress: Optional[ProgressCallback] = None,
) -> dict:
    """
    End-to-end ingestion pipeline with optional progress reporting.
    
    Args:
        doc_id: Unique document identifier
        file_path: Path to the PDF file
        bank: Bank/source (optional - auto-extracted if not provided)
        asset_class: Asset class (optional - auto-extracted if not provided)
        report_date: ISO date string (optional - auto-extracted if not provided)
        title: Document title (optional)
        on_progress: Async callback(step_name, percent, detail)
        
    Returns:
        Dictionary with ingestion statistics and extracted metadata
    """
    async def emit(step: str, percent: int, detail: str = ""):
        if on_progress:
            await on_progress(step, percent, detail)
        else:
            # Default logging if no callback
            logger.info(f"[{percent}%] {step}: {detail}")

    result = {
        "doc_id": doc_id,
        "title": title,
        "bank": bank,
        "asset_class": asset_class, 
        "report_date": report_date,
        "segments": 0,
        "chunks": 0,
        "recommendations": 0,
        "status": "processing"
    }

    vector_store: Optional[ResearchVectorStore] = None
    
    ingestion_provider_name = "Mistral OCR"

    try:
        logger.info(f"Starting ingestion for document {doc_id}")
        
        # 1. Parse PDF to segments using Mistral OCR (0-25%)
        ingestion_provider_name = "Mistral OCR"
        await emit("ocr", 5, "Reading PDF with Mistral OCR...")
        segments = await parse_pdf_to_segments(doc_id=doc_id, file_path=file_path)
        
        if not segments:
            logger.warning(f"No segments extracted from {file_path}")
            result["status"] = "empty"
            await emit("error", 100, "No content found in PDF")
            return result
            
        result["segments"] = len(segments)
        await emit("ocr", 25, f"Extracted {len(segments)} segments")
        
        # 2. Auto-extract metadata if not provided (25-35%)
        ingestion_provider_name = "Mistral metadata extraction"
        await emit("metadata", 28, "Extracting metadata...")
        if not all([bank, asset_class, report_date]):
            first_pages_text = "\n".join([s.text for s in segments[:3]])
            metadata = await extract_metadata_from_content(first_pages_text)
            
            if metadata:
                bank = bank or metadata.bank
                asset_class = asset_class or metadata.asset_class
                report_date = report_date or metadata.report_date
                title = title or metadata.title
            else:
                # Fallback defaults
                bank = bank or "UNKNOWN"
                asset_class = asset_class or "unknown"
                report_date = report_date or "UNKNOWN"
                
        # Update result with final metadata
        result["bank"] = bank
        result["asset_class"] = asset_class
        result["report_date"] = report_date
        result["title"] = title
        
        await emit("metadata", 35, f"{bank} • {asset_class}")
        
        # 3. Build chunks using Smart Chunker (35-45%)
        ingestion_provider_name = "ingestion pipeline"
        await emit("chunking", 38, "Building smart chunks...")
        chunks = build_chunks(
            doc_id=doc_id,
            bank=bank,
            asset_class=asset_class,
            report_date=report_date,
            segments=segments,
        )
        result["chunks"] = len(chunks)
        
        if not chunks:
            result["status"] = "no_chunks"
            await emit("error", 100, "Could not create chunks")
            return result
            
        await emit("chunking", 45, f"Created {len(chunks)} chunks")
        
        # 4. Index in vector store (45-75%)
        # Note: Vector store handles embedding generation internally
        ingestion_provider_name = "Mistral embeddings"
        await emit("indexing", 50, "Indexing in vector database...")
        vector_store = get_vector_store()
        await vector_store.index_chunks(chunks)
        await emit("indexing", 75, f"Indexed {len(chunks)} chunks")
        
        # 5. Extract structured recommendations (75-95%)
        ingestion_provider_name = "Mistral recommendations"
        await emit("recommendations", 78, "Extracting structured recommendations...")
        raw_markdown = "\n\n".join([s.text for s in segments])
        recommendations: List[Recommendation] = await extract_recommendations_with_mistral(
            doc_id=doc_id,
            bank=bank,
            raw_markdown=raw_markdown,
        )
        result["recommendations"] = len(recommendations)
        
        # 6. Store recommendations
        if recommendations:
            recommendation_store = get_recommendation_store()
            await recommendation_store.save_recommendations(recommendations)
            
        await emit("recommendations", 95, f"Found {len(recommendations)} recommendations")
        
        # Complete
        result["status"] = "success"
        logger.info(f"Ingestion complete for {doc_id}")
        await emit("complete", 100, "Processing complete!")
        
        return result
        
    except Exception as e:
        error_message = format_ingestion_error(e, provider_name=ingestion_provider_name)
        logger.error(f"Ingestion error for {doc_id}: {e}")
        result["status"] = "error"
        result["error"] = error_message
        result["cleanup"] = _cleanup_failed_ingestion(doc_id, file_path, vector_store)
        await emit("error", 100, error_message)
        return result
