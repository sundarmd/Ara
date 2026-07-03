import json
import tempfile
import unittest
from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock, patch

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


class UploadCompletionTests(unittest.IsolatedAsyncioTestCase):
    async def test_successful_upload_emits_enriched_complete_event_once(self):
        upload = FakeUploadFile("report.pdf", b"%PDF-1.4\nreport")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = None
        doc_store.get_document_by_filename.return_value = None

        async def ingest_pdf(**kwargs):
            await kwargs["on_progress"]("ocr", 5, "Reading PDF with Mistral OCR...")
            await kwargs["on_progress"]("complete", 100, "Processing complete!")
            return {
                "status": "success",
                "bank": "GS",
                "asset_class": "rates",
                "report_date": "2026-07-02",
                "title": "Rates Outlook",
                "chunks": 7,
                "recommendations": 2,
            }

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "ingest_pdf", new=AsyncMock(side_effect=ingest_pdf)),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)

        complete_events = [event for event in events if event.get("step") == "complete"]
        self.assertEqual(len(complete_events), 1)
        complete = complete_events[0]
        self.assertEqual(complete["file"], "report.pdf")
        self.assertEqual(complete["percent"], 100)
        self.assertEqual(complete["detail"], "Processing complete")
        self.assertEqual(complete["bank"], "GS")
        self.assertEqual(complete["asset_class"], "rates")
        self.assertEqual(complete["report_date"], "2026-07-02")
        self.assertEqual(complete["chunk_count"], 7)
        self.assertEqual(complete["recommendation_count"], 2)
        self.assertIn("doc_id", complete)
        self.assertEqual(events[-1]["step"], "done")

    async def test_successful_upload_complete_event_includes_warnings(self):
        upload = FakeUploadFile("report.pdf", b"%PDF-1.4\nreport")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = None
        doc_store.get_document_by_filename.return_value = None

        ingest_pdf = AsyncMock(return_value={
            "status": "success",
            "bank": "GS",
            "asset_class": "rates",
            "report_date": "2026-07-02",
            "title": "Rates Outlook",
            "chunks": 7,
            "recommendations": 0,
            "warnings": ["Recommendation extraction failed; document search is still available."],
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)

        complete = [event for event in events if event.get("step") == "complete"][0]
        self.assertEqual(
            complete["warnings"],
            ["Recommendation extraction failed; document search is still available."],
        )

    async def test_upload_error_event_includes_type_and_code(self):
        upload = FakeUploadFile("report.pdf", b"%PDF-1.4\nreport")
        doc_store = Mock()
        doc_store.check_duplicate.return_value = None
        doc_store.get_document_by_filename.return_value = None

        ingest_pdf = AsyncMock(return_value={
            "status": "error",
            "error": "Mistral OCR rate limit reached. Wait a moment and try again.",
        })

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                events = await collect_events(response)

        error_event = [event for event in events if event.get("step") == "error"][0]
        self.assertEqual(error_event["type"], "error")
        self.assertEqual(error_event["code"], "ingestion_error")
        self.assertEqual(
            error_event["detail"],
            "Mistral OCR rate limit reached. Wait a moment and try again.",
        )
