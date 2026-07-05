import hashlib
import json
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from services.document_store import DocumentRecord

import main


_MISSING = object()


@contextmanager
def override_setting(name, value):
    original = getattr(main.settings, name, _MISSING)
    object.__setattr__(main.settings, name, value)
    try:
        yield
    finally:
        if original is _MISSING:
            object.__delattr__(main.settings, name)
        else:
            object.__setattr__(main.settings, name, original)


class FakeUploadFile:
    def __init__(self, filename, content, content_type="application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size=-1):
        if self._offset >= len(self._content):
            return b""

        if size is None or size < 0:
            size = len(self._content) - self._offset

        chunk = self._content[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


async def collect_events(response):
    body_parts = []
    async for chunk in response.body_iterator:
        body_parts.append(chunk.decode() if isinstance(chunk, bytes) else chunk)

    events = []
    for line in "".join(body_parts).splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line.removeprefix("data: ")))
    return events


def make_document_record(doc_id, file_hash, filename):
    return DocumentRecord(
        doc_id=doc_id,
        file_hash=file_hash,
        filename=filename,
        bank="GS",
        asset_class="rates",
        report_date="2026-07-02",
        title=filename,
        indexed_at="2026-07-02T00:00:00",
        chunk_count=3,
    )


class UploadDuplicateTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_same_hash_before_ocr_even_with_different_filename(self):
        content = b"%PDF-1.4\nsame content"
        file_hash = hashlib.sha256(content).hexdigest()
        upload = FakeUploadFile("copy.pdf", content)
        duplicate_doc = make_document_record("existing-doc", file_hash, "original.pdf")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = duplicate_doc
        doc_store.get_document_by_filename.return_value = None
        ingest_pdf = AsyncMock(return_value={"status": "success"})
        vector_store = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "get_vector_store", return_value=vector_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)
                spooled_pdfs = list(Path(tmpdir).glob("*.pdf"))

        self.assertEqual(events[0]["step"], "duplicate")
        self.assertIn("original.pdf", events[0]["detail"])
        self.assertEqual(events[0]["bank"], "GS")
        self.assertEqual(events[0]["asset_class"], "rates")
        self.assertEqual(events[-1]["step"], "done")
        self.assertEqual(spooled_pdfs, [])
        doc_store.check_duplicate.assert_called_once_with(file_hash)
        doc_store.get_document_by_filename.assert_not_called()
        doc_store.delete_document.assert_not_called()
        vector_store.delete_document.assert_not_called()
        ingest_pdf.assert_not_awaited()

    async def test_upload_replaces_same_filename_when_hash_differs(self):
        old_hash = "old-hash"
        content = b"%PDF-1.4\nnew content"
        new_hash = hashlib.sha256(content).hexdigest()
        upload = FakeUploadFile("report.pdf", content)
        existing_doc = make_document_record("old-doc", old_hash, "report.pdf")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = None
        doc_store.get_document_by_filename.return_value = existing_doc
        vector_store = Mock()
        recommendation_store = Mock()
        recommendation_store.delete_by_doc_id.return_value = 2
        ingest_pdf = AsyncMock(return_value={
            "status": "success",
            "bank": "MS",
            "asset_class": "credit",
            "report_date": "2026-07-02",
            "title": "New Report",
            "chunks": 4,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reports_dir = tmp_path / "reports"
            images_root = tmp_path / "images"
            tables_root = tmp_path / "tables"
            old_images_dir = images_root / "old-doc"
            old_tables_dir = tables_root / "old-doc"
            reports_dir.mkdir()
            old_images_dir.mkdir(parents=True)
            old_tables_dir.mkdir(parents=True)
            old_path = reports_dir / "old-doc.pdf"
            old_path.write_bytes(b"%PDF-1.4\nold content")
            (old_images_dir / "page-1.png").write_bytes(b"image")
            (old_tables_dir / "table-1.md").write_text("| A | B |", encoding="utf-8")
            with (
                override_setting("DATA_DIR", str(reports_dir)),
                override_setting("REPORTS_DIR", str(reports_dir)),
                override_setting("IMAGES_DIR", str(images_root)),
                override_setting("TABLES_DIR", str(tables_root)),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "get_vector_store", return_value=vector_store),
                patch.object(main, "get_recommendation_store", return_value=recommendation_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)

        self.assertEqual(events[-1]["step"], "done")
        doc_store.check_duplicate.assert_called_once_with(new_hash)
        doc_store.get_document_by_filename.assert_called_once_with("report.pdf")
        vector_store.delete_document.assert_called_once_with("old-doc")
        recommendation_store.delete_by_doc_id.assert_called_once_with("old-doc")
        doc_store.delete_document.assert_called_once_with("old-doc")
        self.assertFalse(old_path.exists())
        self.assertFalse(old_images_dir.exists())
        self.assertFalse(old_tables_dir.exists())
        ingest_pdf.assert_awaited_once()
        add_kwargs = doc_store.add_document.call_args.kwargs
        self.assertEqual(add_kwargs["file_hash"], new_hash)
        self.assertEqual(add_kwargs["filename"], "report.pdf")

    async def test_upload_replacement_cleanup_failure_aborts_new_ingestion(self):
        old_hash = "old-hash"
        content = b"%PDF-1.4\nnew content"
        new_hash = hashlib.sha256(content).hexdigest()
        upload = FakeUploadFile("report.pdf", content)
        existing_doc = make_document_record("old-doc", old_hash, "report.pdf")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = None
        doc_store.get_document_by_filename.return_value = existing_doc
        cleanup_failure = RuntimeError("vector cleanup failed")
        ingest_pdf = AsyncMock(return_value={
            "status": "success",
            "bank": "MS",
            "asset_class": "credit",
            "report_date": "2026-07-02",
            "title": "New Report",
            "chunks": 4,
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "_delete_document_artifacts", side_effect=cleanup_failure) as cleanup,
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)
                spooled_pdfs = list(Path(tmpdir).glob("*.pdf"))

        error_events = [event for event in events if event.get("step") == "error"]
        self.assertEqual(events[0]["step"], "preprocessing")
        self.assertEqual(len(error_events), 1)
        self.assertEqual(error_events[0]["code"], "replacement_cleanup_error")
        self.assertIn("Could not replace existing document", error_events[0]["detail"])
        self.assertEqual(events[-1]["step"], "done")
        self.assertEqual(spooled_pdfs, [])
        doc_store.check_duplicate.assert_called_once_with(new_hash)
        doc_store.get_document_by_filename.assert_called_once_with("report.pdf")
        cleanup.assert_called_once_with(existing_doc, doc_store=doc_store)
        ingest_pdf.assert_not_awaited()
        doc_store.add_document.assert_not_called()
