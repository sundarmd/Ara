import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services import document_reader


class DocumentReaderImageTests(unittest.TestCase):
    def test_save_page_images_uses_per_document_directory(self):
        image_data = base64.b64encode(b"image-bytes").decode("ascii")
        images = [
            {
                "id": "img-1",
                "image_base64": f"data:image/png;base64,{image_data}",
            }
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.object(document_reader.settings, "IMAGES_DIR", tmpdir):
                image_paths = document_reader._save_page_images("doc-1", 2, images)

            expected_path = Path(tmpdir) / "doc-1" / "2_0.png"
            old_flat_path = Path(tmpdir) / "doc-1_2_0.png"

            self.assertEqual(image_paths["img-1"], str(expected_path))
            self.assertTrue(expected_path.exists())
            self.assertFalse(old_flat_path.exists())


class DocumentReaderMarkdownTests(unittest.TestCase):
    def test_parse_markdown_classifies_blocks_and_tracks_section(self):
        markdown = "\n\n".join([
            "# Rates Strategy",
            "Duration should outperform into year-end.",
            "| Tenor | View |\n|---|---|\n| 10Y | Long |",
            "![Curve chart](img-1)",
        ])

        segments = document_reader._parse_markdown_to_segments(
            doc_id="doc-1",
            page=7,
            markdown=markdown,
            current_section=None,
            image_paths={"img-1": "/tmp/chart.png"},
        )

        self.assertEqual(
            [segment.segment_type for segment in segments],
            ["heading", "body", "table", "caption"],
        )
        self.assertEqual(segments[1].section, "Rates Strategy")
        self.assertEqual(segments[2].section, "Rates Strategy")
        self.assertEqual(segments[3].text, "Curve chart")
        self.assertEqual(segments[3].image_path, "/tmp/chart.png")
