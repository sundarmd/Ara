import os
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager

from config.settings import settings
from services.document_store import DocumentStore
from services.recommendations import RecommendationStore


_MISSING = object()


@contextmanager
def override_setting(name, value):
    original = getattr(settings, name, _MISSING)
    object.__setattr__(settings, name, value)
    try:
        yield
    finally:
        if original is _MISSING:
            object.__delattr__(settings, name)
        else:
            object.__setattr__(settings, name, original)


class DataPathTests(unittest.TestCase):
    def test_document_store_default_db_path_is_not_inside_reports_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = os.path.join(tmpdir, "reports")
            with (
                override_setting("DATA_ROOT", tmpdir),
                override_setting("DATA_DIR", reports_dir),
                override_setting("REPORTS_DIR", reports_dir),
                override_setting("DOCUMENTS_DB_PATH", None),
            ):
                store = DocumentStore()

            self.assertEqual(store.db_path, os.path.join(tmpdir, "documents.db"))
            self.assertTrue(os.path.exists(store.db_path))
            self.assertFalse(os.path.exists(os.path.join(reports_dir, "documents.db")))

    def test_recommendation_store_default_db_path_is_not_inside_reports_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = os.path.join(tmpdir, "reports")
            with (
                override_setting("DATA_ROOT", tmpdir),
                override_setting("DATA_DIR", reports_dir),
                override_setting("REPORTS_DIR", reports_dir),
                override_setting("RECOMMENDATIONS_DB_PATH", None),
            ):
                store = RecommendationStore()

            self.assertEqual(store.db_path, os.path.join(tmpdir, "recommendations.db"))
            self.assertTrue(os.path.exists(store.db_path))
            self.assertFalse(os.path.exists(os.path.join(reports_dir, "recommendations.db")))

    def test_document_store_copies_legacy_reports_db_to_data_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = os.path.join(tmpdir, "reports")
            legacy_store = DocumentStore(db_path=os.path.join(reports_dir, "documents.db"))
            legacy_store.add_document(
                doc_id="legacy-doc",
                file_hash="legacy-hash",
                filename="legacy.pdf",
                bank="GS",
                asset_class="rates",
                report_date="2026-07-02",
            )

            with (
                override_setting("DATA_ROOT", tmpdir),
                override_setting("DATA_DIR", reports_dir),
                override_setting("REPORTS_DIR", reports_dir),
                override_setting("DOCUMENTS_DB_PATH", None),
            ):
                store = DocumentStore()

            self.assertEqual(store.db_path, os.path.join(tmpdir, "documents.db"))
            self.assertIsNotNone(store.get_document("legacy-doc"))
            self.assertTrue(os.path.exists(os.path.join(reports_dir, "documents.db")))

    def test_recommendation_store_copies_legacy_reports_db_to_data_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = os.path.join(tmpdir, "reports")
            legacy_db_path = os.path.join(reports_dir, "recommendations.db")
            legacy_store = RecommendationStore(db_path=legacy_db_path)
            with sqlite3.connect(legacy_store.db_path) as conn:
                conn.execute("""
                    INSERT INTO recommendations
                    (id, doc_id, source_type, bank, asset_class, stance, rationale)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    "rec-1",
                    "legacy-doc",
                    "sell_side",
                    "GS",
                    "rates",
                    "OW",
                    "Legacy recommendation",
                ))
                conn.commit()

            with (
                override_setting("DATA_ROOT", tmpdir),
                override_setting("DATA_DIR", reports_dir),
                override_setting("REPORTS_DIR", reports_dir),
                override_setting("RECOMMENDATIONS_DB_PATH", None),
            ):
                store = RecommendationStore()

            self.assertEqual(store.db_path, os.path.join(tmpdir, "recommendations.db"))
            with sqlite3.connect(store.db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM recommendations WHERE id = ?",
                    ("rec-1",),
                ).fetchone()[0]
            self.assertEqual(count, 1)
            self.assertTrue(os.path.exists(legacy_db_path))
