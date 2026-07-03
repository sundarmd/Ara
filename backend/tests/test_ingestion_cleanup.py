import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx

from models.schemas import Chunk, Segment
from services import ingestion


def http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("request failed", request=request, response=response)


class IngestionCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_recommendation_extraction_input_includes_page_and_section_markers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "doc-1.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")

            segments = [
                Segment(
                    doc_id="doc-1",
                    page=7,
                    segment_type="body",
                    text="Long duration versus cash.",
                    section="Rates Strategy",
                ),
                Segment(
                    doc_id="doc-1",
                    page=8,
                    segment_type="body",
                    text="Neutral credit spreads.",
                ),
            ]
            chunks = [
                Chunk(
                    id="chunk-1",
                    doc_id="doc-1",
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                    page_start=7,
                    page_end=8,
                    section="Rates Strategy",
                    segment_types=["body"],
                    text="Long duration versus cash.\nNeutral credit spreads.",
                )
            ]

            vector_store = Mock()
            vector_store.index_chunks = AsyncMock()
            extract_recommendations = AsyncMock(return_value=[])

            with (
                patch.object(ingestion, "parse_pdf_to_segments", new=AsyncMock(return_value=segments)),
                patch.object(ingestion, "build_chunks", return_value=chunks),
                patch.object(ingestion, "get_vector_store", return_value=vector_store),
                patch.object(
                    ingestion,
                    "extract_recommendations_with_mistral",
                    new=extract_recommendations,
                ),
            ):
                result = await ingestion.ingest_pdf(
                    doc_id="doc-1",
                    file_path=str(file_path),
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                )

        self.assertEqual(result["status"], "success")
        raw_markdown = extract_recommendations.call_args.kwargs["raw_markdown"]
        self.assertIn("[Page 7 | Section: Rates Strategy]", raw_markdown)
        self.assertIn("[Page 8]", raw_markdown)
        self.assertLess(
            raw_markdown.index("[Page 7 | Section: Rates Strategy]"),
            raw_markdown.index("Long duration versus cash."),
        )
        self.assertLess(
            raw_markdown.index("[Page 8]"),
            raw_markdown.index("Neutral credit spreads."),
        )

    async def test_ingestion_failure_cleans_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "doc-1.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")
            images_root = tmp_path / "images"
            image_dir = images_root / "doc-1"
            image_dir.mkdir(parents=True)
            (image_dir / "page-1.png").write_bytes(b"image")
            tables_root = tmp_path / "tables"
            table_dir = tables_root / "doc-1"
            table_dir.mkdir(parents=True)
            (table_dir / "page-1.md").write_text("| A | B |", encoding="utf-8")

            segments = [
                Segment(
                    doc_id="doc-1",
                    page=1,
                    segment_type="body",
                    text="Research report body.",
                )
            ]
            chunks = [
                Chunk(
                    id="chunk-1",
                    doc_id="doc-1",
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                    page_start=1,
                    page_end=1,
                    section=None,
                    segment_types=["body"],
                    text="Research report body.",
                )
            ]

            vector_store = Mock()
            vector_store.index_chunks = AsyncMock()
            recommendation_store = Mock()

            with (
                patch.object(ingestion.settings, "IMAGES_DIR", str(images_root)),
                patch.object(ingestion.settings, "TABLES_DIR", str(tables_root)),
                patch.object(ingestion, "parse_pdf_to_segments", new=AsyncMock(return_value=segments)),
                patch.object(ingestion, "build_chunks", return_value=chunks),
                patch.object(ingestion, "get_vector_store", return_value=vector_store),
                patch.object(
                    ingestion,
                    "extract_recommendations_with_mistral",
                    new=AsyncMock(side_effect=RuntimeError("recommendation failure")),
                ),
                patch.object(ingestion, "get_recommendation_store", return_value=recommendation_store),
            ):
                result = await ingestion.ingest_pdf(
                    doc_id="doc-1",
                    file_path=str(file_path),
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                )

        self.assertEqual(result["status"], "error")
        self.assertIn("recommendation failure", result["error"])
        vector_store.delete_document.assert_called_once_with("doc-1")
        recommendation_store.delete_by_doc_id.assert_called_once_with("doc-1")
        self.assertFalse(file_path.exists())
        self.assertFalse(image_dir.exists())
        self.assertFalse(table_dir.exists())

    async def test_ingestion_errors_use_current_provider_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "doc-1.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")

            segments = [
                Segment(
                    doc_id="doc-1",
                    page=1,
                    segment_type="body",
                    text="Research report body.",
                )
            ]
            chunks = [
                Chunk(
                    id="chunk-1",
                    doc_id="doc-1",
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                    page_start=1,
                    page_end=1,
                    section=None,
                    segment_types=["body"],
                    text="Research report body.",
                )
            ]
            progress_events = []

            async def on_progress(step, percent, detail):
                progress_events.append({
                    "step": step,
                    "percent": percent,
                    "detail": detail,
                })

            vector_store = Mock()
            vector_store.index_chunks = AsyncMock(side_effect=http_status_error(429))
            recommendation_store = Mock()

            with (
                patch.object(ingestion, "parse_pdf_to_segments", new=AsyncMock(return_value=segments)),
                patch.object(ingestion, "build_chunks", return_value=chunks),
                patch.object(ingestion, "get_vector_store", return_value=vector_store),
                patch.object(ingestion, "get_recommendation_store", return_value=recommendation_store),
            ):
                result = await ingestion.ingest_pdf(
                    doc_id="doc-1",
                    file_path=str(file_path),
                    bank="GS",
                    asset_class="rates",
                    report_date="2026-01-01",
                    on_progress=on_progress,
                )

        self.assertEqual(result["status"], "error")
        self.assertEqual(
            result["error"],
            "Mistral embeddings rate limit reached. Wait a moment and try again.",
        )
        self.assertEqual(
            progress_events[-1]["detail"],
            "Mistral embeddings rate limit reached. Wait a moment and try again.",
        )
