"""
SQLite-based document store for tracking indexed documents.
Provides duplicate detection via SHA256 hash.
"""
import sqlite3
import hashlib
import os
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass

from config.settings import settings


@dataclass
class DocumentRecord:
    """A record of an indexed document."""
    doc_id: str
    file_hash: str
    filename: str
    bank: str
    asset_class: str
    report_date: str
    title: Optional[str]
    indexed_at: str
    chunk_count: int = 0


class DocumentStore:
    """SQLite store for tracking indexed documents."""
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or os.path.join(settings.DATA_DIR, "documents.db")
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    doc_id TEXT PRIMARY KEY,
                    file_hash TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    bank TEXT NOT NULL,
                    asset_class TEXT NOT NULL,
                    report_date TEXT NOT NULL,
                    title TEXT,
                    indexed_at TEXT NOT NULL,
                    chunk_count INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON documents(file_hash)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_bank ON documents(bank)")
            conn.commit()
    
    @staticmethod
    def compute_hash(content: bytes) -> str:
        """Compute SHA256 hash of file content."""
        return hashlib.sha256(content).hexdigest()
    
    def check_duplicate(self, file_hash: str) -> Optional[DocumentRecord]:
        """Check if a document with this hash already exists."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM documents WHERE file_hash = ?", 
                (file_hash,)
            )
            row = cursor.fetchone()
            if row:
                return DocumentRecord(**dict(row))
        return None
    
    def add_document(
        self,
        doc_id: str,
        file_hash: str,
        filename: str,
        bank: str,
        asset_class: str,
        report_date: str,
        title: Optional[str] = None,
        chunk_count: int = 0,
    ) -> DocumentRecord:
        """Add a new document record."""
        indexed_at = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO documents 
                (doc_id, file_hash, filename, bank, asset_class, report_date, title, indexed_at, chunk_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (doc_id, file_hash, filename, bank, asset_class, report_date, title, indexed_at, chunk_count))
            conn.commit()
        
        return DocumentRecord(
            doc_id=doc_id,
            file_hash=file_hash,
            filename=filename,
            bank=bank,
            asset_class=asset_class,
            report_date=report_date,
            title=title,
            indexed_at=indexed_at,
            chunk_count=chunk_count,
        )
    
    def update_chunk_count(self, doc_id: str, chunk_count: int):
        """Update the chunk count for a document."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE documents SET chunk_count = ? WHERE doc_id = ?",
                (chunk_count, doc_id)
            )
            conn.commit()
    
    def get_all_documents(self) -> List[DocumentRecord]:
        """Get all indexed documents."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM documents ORDER BY indexed_at DESC")
            return [DocumentRecord(**dict(row)) for row in cursor.fetchall()]
    
    def get_document(self, doc_id: str) -> Optional[DocumentRecord]:
        """Get a document by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            if row:
                return DocumentRecord(**dict(row))
        return None
    
    def get_document_by_filename(self, filename: str) -> Optional[DocumentRecord]:
        """Get a document by filename."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM documents WHERE filename = ?", (filename,))
            row = cursor.fetchone()
            if row:
                return DocumentRecord(**dict(row))
        return None
    
    def delete_document(self, doc_id: str) -> bool:
        """Delete a document record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))
            conn.commit()
            return cursor.rowcount > 0


# Singleton instance
_document_store: Optional[DocumentStore] = None


def get_document_store() -> DocumentStore:
    """Get or create the document store singleton."""
    global _document_store
    if _document_store is None:
        _document_store = DocumentStore()
    return _document_store
