import os
import uuid
import logging
import json
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
import uvicorn

from config.settings import settings, ensure_directories
from services.ingestion import ingest_pdf
from services.recommendations import get_recommendation_store
from services.chat import stream_chat_rag
from services.document_store import get_document_store, DocumentStore
from services.database import get_vector_store
from models.schemas import ChatRequest

# Configure JSON Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj)

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])

# Lifespan Context Manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize directories and services on startup."""
    ensure_directories()
    logger.info("Application started, directories initialized")

    # Auto-seed internal data if analysts table is empty (prevents duplicates)
    try:
        store = get_recommendation_store()
        analysts = await store.get_analysts()
        if not analysts:
            logger.info("No analysts found, seeding internal mock data...")
            from scripts.seed_internal_data import seed_data
            await seed_data()
            logger.info("Internal mock data seeded successfully")
        else:
            logger.info(f"Found {len(analysts)} existing analysts, skipping seed")
    except Exception as e:
        logger.warning(f"Auto-seed check failed (non-critical): {e}")

    yield
    # Cleanup if needed
    logger.info("Application shutting down")

# Initialize FastAPI app
app = FastAPI(
    title="Agentic AI Research Assistant",
    version="1.0.0",
    description="Multi-agent AI assistant for sell-side research report analysis",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/upload")
async def upload_files(
    files: List[UploadFile] = File(None),  # Accept multiple files
    file: UploadFile = File(None),         # Accept single file (frontend fallback)
    bank: Optional[str] = Form(None),
    asset_class: Optional[str] = Form(None),
    report_date: Optional[str] = Form(None),
):
    """
    Upload and index PDFs with real-time SSE progress streaming.
    Emits events after each processing step completes.
    """
    # Normalize files input (handle both 'files' and 'file' fields)
    full_file_list = []
    if files:
        full_file_list.extend(files)
    if file:
        full_file_list.append(file)
        
    if not full_file_list:
        raise HTTPException(status_code=400, detail="No file provided")

    # Read all files into memory immediately to avoid "closed file" errors in StreamingResponse
    file_data = []
    for f in full_file_list:
        content = await f.read()
        file_data.append({
            "filename": f.filename,
            "content": content
        })

    async def generate():
        doc_store = get_document_store()
        total_files = len(file_data)
        
        for idx, item in enumerate(file_data):
            filename = item["filename"] or f"file_{idx}"
            contents = item["content"]
            
            # Validate file type
            if not filename.lower().endswith(".pdf"):
                yield f"data: {json.dumps({'file': filename, 'step': 'error', 'percent': 100, 'detail': 'Only PDF files supported'})}\n\n"
                continue
            
            # Check for duplicate
            file_hash = DocumentStore.compute_hash(contents)
            existing_doc = doc_store.get_document_by_filename(filename)
            
            if existing_doc:
                yield f"data: {json.dumps({'file': filename, 'step': 'preprocessing', 'percent': 10, 'detail': f'Replacing existing version...'})}\n\n"
                try:
                    v_store = get_vector_store()
                    v_store.delete_document(existing_doc.doc_id)
                    doc_store.delete_document(existing_doc.doc_id)
                    old_path = os.path.join(settings.DATA_DIR, f"{existing_doc.doc_id}.pdf")
                    if os.path.exists(old_path):
                        os.remove(old_path)
                except Exception as e:
                    logger.warning(f"Cleanup failed for {filename}: {e}")

            # Prepare for Ingestion
            doc_id = str(uuid.uuid4())
            stored_path = os.path.join(settings.DATA_DIR, f"{doc_id}.pdf")
            
            try:
                os.makedirs(settings.DATA_DIR, exist_ok=True)
                with open(stored_path, "wb") as f:
                    f.write(contents)
                
                # --- Queue-based Streaming Implementation ---
                import asyncio
                queue = asyncio.Queue()
                
                async def on_progress(step, percent, detail):
                    await queue.put({
                        "file": filename,
                        "step": step,
                        "percent": percent,
                        "detail": detail
                    })
                
                # Run ingestion in background task
                task = asyncio.create_task(
                    ingest_pdf(
                        doc_id=doc_id, 
                        file_path=stored_path, 
                        title=filename,
                        bank=bank,
                        asset_class=asset_class,
                        report_date=report_date,
                        on_progress=on_progress
                    )
                )
                
                # Loop while task is running to consume queue
                while not task.done():
                    try:
                        # Wait for next event or check task status every 0.1s
                        data = await asyncio.wait_for(queue.get(), timeout=0.1)
                        yield f"data: {json.dumps(data)}\n\n"
                    except asyncio.TimeoutError:
                        continue
                        
                # Flush any remaining items in queue
                while not queue.empty():
                    data = await queue.get()
                    yield f"data: {json.dumps(data)}\n\n"
                
                # Check final result
                result = await task
                
                if result.get("status") == "success":
                    # Record in document store
                    file_hash = DocumentStore.compute_hash(contents)
                    doc_store.add_document(
                        doc_id=doc_id,
                        file_hash=file_hash,
                        filename=filename,
                        bank=result.get("bank", "Top-tier Bank"),
                        asset_class=result.get("asset_class", "multi_asset"),
                        report_date=result.get("report_date") or "UNKNOWN",
                        title=result.get("title", filename),
                        chunk_count=result.get("chunks", 0),
                    )
                elif result.get("status") == "error":
                     yield f"data: {json.dumps({'file': filename, 'step': 'error', 'percent': 100, 'detail': result.get('error', 'Unknown Error')})}\n\n"

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                if os.path.exists(stored_path):
                    os.remove(stored_path)
                yield f"data: {json.dumps({'file': filename, 'step': 'error', 'percent': 100, 'detail': str(e)})}\n\n"
        
        # Signal end of stream
        yield f"data: {json.dumps({'step': 'done', 'total': total_files})}\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/files/{filename}")
async def serve_pdf(filename: str):
    """
    Serve uploaded PDF files from the data directory.
    Supports deep linking to specific pages via #page= fragment.
    """
    # Security: Only allow PDF files
    if not filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Prevent directory traversal attacks
    if '/' in filename or '\\' in filename or '..' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = os.path.join(settings.DATA_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"}
    )


@app.get("/documents/{doc_id}/file")
async def serve_document_file(doc_id: str):
    """
    Serve a stored PDF by document ID.
    Resolves metadata through DocumentStore before opening DATA_DIR/{doc_id}.pdf.
    """
    doc_store = get_document_store()
    doc = doc_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = os.path.join(settings.DATA_DIR, f"{doc.doc_id}.pdf")
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=doc.filename,
        content_disposition_type="inline",
    )


@app.get("/documents")
async def list_documents():
    """Get all indexed documents."""
    doc_store = get_document_store()
    documents = doc_store.get_all_documents()
    return {
        "documents": [
            {
                "doc_id": d.doc_id,
                "filename": d.filename,
                "bank": d.bank,
                "asset_class": d.asset_class,
                "report_date": d.report_date,
                "title": d.title,
                "indexed_at": d.indexed_at,
                "chunk_count": d.chunk_count,
            }
            for d in documents
        ],
        "total": len(documents),
    }


@app.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    """
    Completely delete a document and all associated data.
    Removes: PDF file, metadata, vector embeddings, recommendations.
    """
    import shutil
    from services.recommendations import get_recommendation_store

    doc_store = get_document_store()
    vector_store = get_vector_store()
    rec_store = get_recommendation_store()

    # Check document exists
    doc = doc_store.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    deleted_items = {
        "doc_id": doc_id,
        "filename": doc.filename,
        "pdf_deleted": False,
        "metadata_deleted": False,
        "vectors_deleted": False,
        "recommendations_deleted": 0,
        "images_deleted": 0
    }

    # 1. Delete PDF file
    pdf_path = os.path.join(settings.DATA_DIR, f"{doc_id}.pdf")
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        deleted_items["pdf_deleted"] = True

    # 2. Delete vector embeddings
    try:
        vector_store.delete_document(doc_id)
        deleted_items["vectors_deleted"] = True
    except Exception as e:
        logger.warning(f"Failed to delete vectors for {doc_id}: {e}")

    # 3. Delete recommendations
    try:
        count = rec_store.delete_by_doc_id(doc_id)
        deleted_items["recommendations_deleted"] = count
    except Exception as e:
        logger.warning(f"Failed to delete recommendations for {doc_id}: {e}")

    # 4. Delete extracted images (if any)
    images_dir = os.path.join(settings.IMAGES_DIR, doc_id)
    if os.path.exists(images_dir):
        image_count = len(os.listdir(images_dir))
        shutil.rmtree(images_dir)
        deleted_items["images_deleted"] = image_count

    # 5. Delete document metadata (last, so we can still reference doc info above)
    deleted_items["metadata_deleted"] = doc_store.delete_document(doc_id)

    logger.info(f"Document deleted: {deleted_items}")
    return deleted_items


@app.get("/debug_search")
async def debug_search(
    q: str = Query(..., description="Search query"),
    n_results: int = Query(5, description="Number of results to return"),
    bank: Optional[str] = Query(None, description="Filter by bank"),
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
):
    """
    Debug endpoint to test vector store search.
    
    Returns top-k chunks matching the query.
    """
    try:
        # Search vector store
        store = get_vector_store()
        results = await store.search(
            query=q,
            n_results=n_results,
            filter_bank=bank,
            filter_asset_class=asset_class,
        )
        
        return {
            "query": q,
            "n_results": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search error: {str(e)}"
        )


@app.get("/stats")
async def get_stats():
    """Get statistics about the indexed documents."""
    try:
        store = get_vector_store()
        stats = store.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting stats: {str(e)}"
        )


@app.post("/chat/stream")
async def chat_stream_endpoint(request: ChatRequest):
    """
    Streaming chat with the research assistant.
    
    Returns Server-Sent Events (SSE) with:
    - thought: Agent reasoning steps
    - token: Response text chunks
    - complete: Final answer with sources and recommendations
    - error: Error information if something goes wrong
    
    Optional filters: bank, asset_class
    """
    return StreamingResponse(
        stream_chat_rag(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.get("/debug_recommendations")
async def debug_recommendations(
    bank: Optional[str] = Query(None, description="Filter by bank"),
    asset_class: Optional[str] = Query(None, description="Filter by asset class"),
    doc_id: Optional[str] = Query(None, description="Filter by document ID"),
    source_type: Optional[str] = Query(None, description="Filter by source type (sell_side, internal, analyst_tracking)"),
):
    """
    Debug endpoint to view extracted recommendations.
    """
    try:
        store = get_recommendation_store()
        recos = await store.get_by_filters(
            bank=bank,
            asset_class=asset_class,
            doc_id=doc_id,
            source_type=source_type,
        )
        return {
            "count": len(recos),
            "recommendations": [r.model_dump() for r in recos]
        }
    except Exception as e:
        logger.error(f"Recommendations error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching recommendations: {str(e)}"
        )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
