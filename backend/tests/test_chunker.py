import os
import tempfile
import unittest
from unittest.mock import patch

from models.schemas import Segment
from services import chunker
from services.chunker import MAX_TOKENS_PER_CHUNK, _get_token_length, build_chunks


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

    def test_heading_starts_new_section_scoped_chunk(self):
        segments = [
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="heading",
                section=None,
                text="Rates Strategy",
            ),
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="body",
                section="Rates Strategy",
                text="Duration can rally as growth slows.",
            ),
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="heading",
                section="Rates Strategy",
                text="FX Strategy",
            ),
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="body",
                section="FX Strategy",
                text="The dollar can weaken as rate spreads compress.",
            ),
        ]

        chunks = build_chunks(
            doc_id="doc-1",
            bank="GS",
            asset_class="macro",
            report_date="2026-01-01",
            segments=segments,
        )

        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0].section, "Rates Strategy")
        self.assertIn("Duration can rally", chunks[0].text)
        self.assertNotIn("FX Strategy", chunks[0].text)
        self.assertEqual(chunks[1].section, "FX Strategy")
        self.assertIn("The dollar can weaken", chunks[1].text)

    def test_oversized_table_is_split_with_artifact_and_row_ranges(self):
        table_rows = [
            f"| Lab measurement {i} | {'calibrated result ' * 16}| pass |"
            for i in range(1, 90)
        ]
        table_text = "\n".join([
            "| Test | Value | Status |",
            "|---|---|---|",
            *table_rows,
        ])

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(chunker.settings, "TABLES_DIR", tmpdir):
                chunks = build_chunks(
                    doc_id="doc-1",
                    bank="BSH",
                    asset_class="lab_data",
                    report_date="2026-01-01",
                    segments=[
                        Segment(
                            doc_id="doc-1",
                            page=5,
                            segment_type="table",
                            section="Measurement Results",
                            text=table_text,
                        )
                    ],
                )

            artifact_path = chunks[0].table_artifact_path
            self.assertIsNotNone(artifact_path)
            self.assertTrue(os.path.exists(artifact_path))
            with open(artifact_path, encoding="utf-8") as artifact_file:
                artifact_text = artifact_file.read()

        self.assertGreater(len(chunks), 1)
        self.assertEqual(artifact_text, table_text)
        self.assertEqual({chunk.table_artifact_path for chunk in chunks}, {artifact_path})
        self.assertEqual(chunks[0].table_row_start, 1)
        self.assertEqual(chunks[-1].table_row_end, len(table_rows))
        self.assertTrue(all(chunk.page_start == 5 and chunk.page_end == 5 for chunk in chunks))
        self.assertTrue(all(chunk.section == "Measurement Results" for chunk in chunks))
        self.assertTrue(all(_get_token_length(chunk.text) <= MAX_TOKENS_PER_CHUNK for chunk in chunks))
        self.assertLess(_get_token_length(chunks[0].text), _get_token_length(table_text))
