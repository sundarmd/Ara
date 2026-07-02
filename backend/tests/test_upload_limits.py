import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

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
        self.read_sizes = []

    async def read(self, size=-1):
        self.read_sizes.append(size)
        if self._offset >= len(self._content):
            return b""

        if size is None or size < 0:
            size = len(self._content) - self._offset

        chunk = self._content[self._offset:self._offset + size]
        self._offset += len(chunk)
        return chunk


async def collect_streaming_body(response):
    parts = []
    async for chunk in response.body_iterator:
        parts.append(chunk.decode() if isinstance(chunk, bytes) else chunk)
    return "".join(parts)


class UploadLimitTests(unittest.IsolatedAsyncioTestCase):
    async def test_upload_rejects_too_many_files_before_reading(self):
        first = FakeUploadFile("first.pdf", b"%PDF-1.4\n")
        second = FakeUploadFile("second.pdf", b"%PDF-1.4\n")

        with override_setting("MAX_UPLOAD_FILES", 1):
            with self.assertRaises(HTTPException) as raised:
                await main.upload_files(files=[first, second], file=None)

        self.assertEqual(raised.exception.status_code, 400)
        self.assertIn("Too many files", raised.exception.detail)
        self.assertEqual(first.read_sizes, [])
        self.assertEqual(second.read_sizes, [])

    async def test_upload_rejects_oversized_file_and_removes_partial_spool(self):
        content = b"%PDF-1.4\n" + (b"a" * (1024 * 1024 + 1))
        upload = FakeUploadFile("large.pdf", content)

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                override_setting("MAX_UPLOAD_MB", 1),
            ):
                with self.assertRaises(HTTPException) as raised:
                    await main.upload_files(files=[upload], file=None)

            spooled_pdfs = list(Path(tmpdir).glob("*.pdf"))

        self.assertEqual(raised.exception.status_code, 413)
        self.assertIn("exceeds", raised.exception.detail)
        self.assertNotIn(-1, upload.read_sizes)
        self.assertEqual(spooled_pdfs, [])

    async def test_upload_rejects_pdf_filename_with_invalid_magic_header(self):
        upload = FakeUploadFile("not-a-pdf.pdf", b"not really a pdf", content_type="application/pdf")
        doc_store = Mock()
        doc_store.get_document_by_filename.return_value = None
        ingest_pdf = AsyncMock(return_value={"status": "success"})

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                body = await collect_streaming_body(response)
                spooled_pdfs = list(Path(tmpdir).glob("*.pdf"))

        self.assertIn("Invalid PDF", body)
        self.assertEqual(spooled_pdfs, [])
        ingest_pdf.assert_not_awaited()

    async def test_upload_rejects_pdf_filename_with_non_pdf_content_type(self):
        upload = FakeUploadFile("report.pdf", b"%PDF-1.4\n", content_type="text/plain")
        doc_store = Mock()
        doc_store.get_document_by_filename.return_value = None
        ingest_pdf = AsyncMock(return_value={"status": "success"})

        with tempfile.TemporaryDirectory() as tmpdir:
            with (
                override_setting("DATA_DIR", tmpdir),
                override_setting("REPORTS_DIR", tmpdir),
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "ingest_pdf", new=ingest_pdf),
            ):
                response = await main.upload_files(files=[upload], file=None)
                body = await collect_streaming_body(response)
                spooled_pdfs = list(Path(tmpdir).glob("*.pdf"))

        self.assertIn("Only PDF uploads are supported", body)
        self.assertEqual(spooled_pdfs, [])
        ingest_pdf.assert_not_awaited()
