import os
import sqlite3
import tempfile
import unittest

from services.document_store import DocumentStore


class DocumentStoreTests(unittest.TestCase):
    def test_hash_duplicate_filename_lookup_and_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = DocumentStore(db_path=os.path.join(tmpdir, "documents.db"))
            file_hash = store.compute_hash(b"same report bytes")

            store.add_document(
                doc_id="doc-1",
                file_hash=file_hash,
                filename="rates.pdf",
                bank="GS",
                asset_class="rates",
                report_date="2026-01-01",
                title="Rates Outlook",
                chunk_count=3,
            )

            duplicate = store.check_duplicate(file_hash)
            by_filename = store.get_document_by_filename("rates.pdf")
            deleted = store.delete_document("doc-1")

        self.assertIsNotNone(duplicate)
        self.assertEqual(duplicate.doc_id, "doc-1")
        self.assertIsNotNone(by_filename)
        self.assertEqual(by_filename.title, "Rates Outlook")
        self.assertTrue(deleted)

    def test_init_db_adds_missing_document_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "documents.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute("""
                    CREATE TABLE documents (
                        doc_id TEXT PRIMARY KEY,
                        file_hash TEXT,
                        filename TEXT,
                        bank TEXT,
                        asset_class TEXT,
                        report_date TEXT,
                        indexed_at TEXT
                    )
                """)
                conn.execute("""
                    INSERT INTO documents
                    (doc_id, file_hash, filename, bank, asset_class, report_date, indexed_at)
                    VALUES ('doc-1', 'hash-1', 'legacy.pdf', 'GS', 'rates', '2026-01-01', '2026-01-02T00:00:00')
                """)
                conn.commit()

            store = DocumentStore(db_path=db_path)
            record = store.get_document("doc-1")
            with sqlite3.connect(db_path) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(documents)")}

        self.assertIn("title", columns)
        self.assertIn("chunk_count", columns)
        self.assertIsNotNone(record)
        self.assertIsNone(record.title)
        self.assertEqual(record.chunk_count, 0)
