import os
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
