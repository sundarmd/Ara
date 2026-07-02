import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from models.schemas import Chunk, Segment
from services import ingestion


class IngestionCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_ingestion_failure_cleans_partial_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            file_path = tmp_path / "doc-1.pdf"
            file_path.write_bytes(b"%PDF-1.4\n")
            images_root = tmp_path / "images"
            image_dir = images_root / "doc-1"
            image_dir.mkdir(parents=True)
            (image_dir / "page-1.png").write_bytes(b"image")

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
