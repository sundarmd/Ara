import unittest

from models.schemas import Segment
from services.chunker import build_chunks


class ChunkerTests(unittest.TestCase):
    def test_build_chunks_preserves_pages_segment_types_and_table_text(self):
        segments = [
            Segment(
                doc_id="doc-1",
                page=2,
                segment_type="heading",
                section=None,
                text="Rates Strategy",
            ),
            Segment(
                doc_id="doc-1",
                page=2,
                segment_type="body",
                section="Rates Strategy",
                text="We expect duration to outperform.",
            ),
            Segment(
                doc_id="doc-1",
                page=3,
                segment_type="table",
                section="Rates Strategy",
                text="| Tenor | View |\n|---|---|\n| 10Y | Long |",
            ),
        ]

        chunks = build_chunks(
            doc_id="doc-1",
            bank="GS",
            asset_class="rates",
            report_date="2026-01-01",
            segments=segments,
        )

        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual(chunk.page_start, 2)
        self.assertEqual(chunk.page_end, 3)
        self.assertEqual(set(chunk.segment_types), {"heading", "body", "table"})
        self.assertIn("| Tenor | View |", chunk.text)
        self.assertEqual(chunk.section, "Rates Strategy")
