import unittest
from unittest.mock import AsyncMock, patch

from models.schemas import Chunk, Segment
from services import ingestion
from services.metadata_extractor import extract_metadata_from_content


class MetadataLLMClient:
    async def get_chat_completion(self, messages, temperature=0.1, max_tokens=200, json_mode=True):
        return {
            "bank": "GS",
            "asset_class": "multi_asset",
            "report_date": "UNKNOWN",
            "title": "Strategy report",
        }


class MetadataFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_metadata_extractor_preserves_unknown_report_date(self):
        text = "Goldman Sachs multi-asset strategy report. " * 10

        with patch("services.llm_client.get_llm_client", return_value=MetadataLLMClient()):
            metadata = await extract_metadata_from_content(text)

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.report_date, "UNKNOWN")

    async def test_ingestion_fallback_uses_unknown_report_date(self):
        segments = [
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="body",
                text="Research report body with no clear publication date.",
            )
        ]
        seen_report_dates = []

        def fake_build_chunks(doc_id, bank, asset_class, report_date, segments):
            seen_report_dates.append(report_date)
            return [
                Chunk(
                    id="chunk-1",
                    doc_id=doc_id,
                    bank=bank,
                    asset_class=asset_class,
                    report_date=report_date,
                    page_start=1,
                    page_end=1,
                    section=None,
                    segment_types=["body"],
                    text=segments[0].text,
                )
            ]

        vector_store = AsyncMock()
        vector_store.index_chunks = AsyncMock()

        with (
            patch.object(ingestion, "parse_pdf_to_segments", new=AsyncMock(return_value=segments)),
            patch.object(ingestion, "extract_metadata_from_content", new=AsyncMock(return_value=None)),
            patch.object(ingestion, "build_chunks", side_effect=fake_build_chunks),
            patch.object(ingestion, "get_vector_store", return_value=vector_store),
            patch.object(ingestion, "extract_recommendations_with_mistral", new=AsyncMock(return_value=[])),
        ):
            result = await ingestion.ingest_pdf(doc_id="doc-1", file_path="/tmp/fake.pdf")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["report_date"], "UNKNOWN")
        self.assertEqual(seen_report_dates, ["UNKNOWN"])
