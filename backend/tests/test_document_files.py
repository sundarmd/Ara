import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

import main
from services import tools


class DocumentFileEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_serve_document_file_resolves_doc_id_through_document_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            stored_pdf = Path(tmpdir) / "doc-1.pdf"
            stored_pdf.write_bytes(b"%PDF-1.4\n")
            doc_store = Mock()
            doc_store.get_document.return_value = SimpleNamespace(
                doc_id="doc-1",
                filename="original-name.pdf",
            )

            with (
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main.settings, "DATA_DIR", tmpdir),
                patch.object(main.settings, "REPORTS_DIR", tmpdir),
            ):
                response = await main.serve_document_file("doc-1")

        doc_store.get_document.assert_called_once_with("doc-1")
        self.assertEqual(response.path, str(stored_pdf))
        self.assertEqual(response.media_type, "application/pdf")

    async def test_serve_document_file_returns_404_for_unknown_doc_id(self):
        doc_store = Mock()
        doc_store.get_document.return_value = None

        with patch.object(main, "get_document_store", return_value=doc_store):
            with self.assertRaises(HTTPException) as raised:
                await main.serve_document_file("missing-doc")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "Document not found")

    async def test_serve_document_file_returns_404_when_pdf_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            doc_store = Mock()
            doc_store.get_document.return_value = SimpleNamespace(
                doc_id="doc-1",
                filename="original-name.pdf",
            )

            with (
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main.settings, "DATA_DIR", tmpdir),
                patch.object(main.settings, "REPORTS_DIR", tmpdir),
            ):
                with self.assertRaises(HTTPException) as raised:
                    await main.serve_document_file("doc-1")

        self.assertEqual(raised.exception.status_code, 404)
        self.assertEqual(raised.exception.detail, "File not found")


class DocumentFileRouteTests(unittest.TestCase):
    def test_legacy_filename_file_route_is_not_registered(self):
        route_paths = {
            (getattr(route, "path", None), method)
            for route in main.app.routes
            for method in getattr(route, "methods", set())
        }

        self.assertNotIn(("/files/{filename}", "GET"), route_paths)

    def test_document_file_route_has_api_key_dependency(self):
        document_file_route = next(
            route
            for route in main.app.routes
            if getattr(route, "path", None) == "/documents/{doc_id}/file"
            and "GET" in getattr(route, "methods", set())
        )

        self.assertTrue(
            any(
                dependency.call is main.verify_api_key
                for dependency in document_file_route.dependant.dependencies
            )
        )


class DocumentDeleteEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_document_removes_table_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            reports_dir = tmp_path / "reports"
            images_root = tmp_path / "images"
            tables_root = tmp_path / "tables"
            image_dir = images_root / "doc-1"
            table_dir = tables_root / "doc-1"
            reports_dir.mkdir()
            image_dir.mkdir(parents=True)
            table_dir.mkdir(parents=True)
            (reports_dir / "doc-1.pdf").write_bytes(b"%PDF-1.4\n")
            (image_dir / "page-1.png").write_bytes(b"image")
            (table_dir / "page-1.md").write_text("| A | B |", encoding="utf-8")

            doc_store = Mock()
            doc_store.get_document.return_value = SimpleNamespace(
                doc_id="doc-1",
                filename="report.pdf",
            )
            doc_store.delete_document.return_value = True
            vector_store = Mock()
            vector_store.delete_document.return_value = 3
            recommendation_store = Mock()
            recommendation_store.delete_by_doc_id.return_value = 2

            with (
                patch.object(main, "get_document_store", return_value=doc_store),
                patch.object(main, "get_vector_store", return_value=vector_store),
                patch.object(main, "get_recommendation_store", return_value=recommendation_store),
                patch.object(main.settings, "DATA_DIR", str(reports_dir)),
                patch.object(main.settings, "REPORTS_DIR", str(reports_dir)),
                patch.object(main.settings, "IMAGES_DIR", str(images_root)),
                patch.object(main.settings, "TABLES_DIR", str(tables_root)),
            ):
                response = await main.delete_document("doc-1")

            self.assertFalse((reports_dir / "doc-1.pdf").exists())
            self.assertFalse(image_dir.exists())
            self.assertFalse(table_dir.exists())
            self.assertEqual(response["vectors_deleted_count"], 3)
            self.assertEqual(response["recommendations_deleted"], 2)
            self.assertEqual(response["images_deleted"], 1)
            self.assertEqual(response["tables_deleted"], 1)
            self.assertTrue(response["metadata_deleted"])

    async def test_delete_document_surfaces_vector_delete_failure(self):
        doc_store = Mock()
        doc_store.get_document.return_value = SimpleNamespace(
            doc_id="doc-1",
            filename="report.pdf",
        )
        vector_store = Mock()
        vector_store.delete_document.side_effect = RuntimeError("verification failed")
        recommendation_store = Mock()

        with (
            patch.object(main, "get_document_store", return_value=doc_store),
            patch.object(main, "get_vector_store", return_value=vector_store),
            patch.object(main, "get_recommendation_store", return_value=recommendation_store),
            patch.object(main.os.path, "exists", return_value=False),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.delete_document("doc-1")

        self.assertEqual(raised.exception.status_code, 500)
        self.assertIn("Failed to delete vectors", raised.exception.detail)
        doc_store.delete_document.assert_not_called()
        recommendation_store.delete_by_doc_id.assert_not_called()


class DocumentFileLinkTests(unittest.IsolatedAsyncioTestCase):
    async def test_knowledge_base_sources_link_to_document_file_endpoint(self):
        search_results = [
            {
                "text": "A report chunk",
                "metadata": {
                    "doc_id": "doc-1",
                    "page_start": 7,
                },
            }
        ]

        with patch.object(tools, "search_documents", AsyncMock(return_value=search_results)):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        source = json.loads(output)["sources"][0]
        self.assertTrue(
            source["metadata"]["url"].endswith("/documents/doc-1/file#page=7"),
            source["metadata"]["url"],
        )

    async def test_knowledge_base_sources_use_public_base_url_when_configured(self):
        search_results = [
            {
                "text": "A report chunk",
                "metadata": {
                    "doc_id": "doc-1",
                    "page_start": 3,
                },
            }
        ]
        doc_store = Mock()
        doc_store.get_document.return_value = SimpleNamespace(
            title="Global Strategy",
            filename="global-strategy.pdf",
        )

        with (
            patch.object(tools, "search_documents", AsyncMock(return_value=search_results)),
            patch.object(tools, "get_document_store", return_value=doc_store),
            patch.object(tools.settings, "API_PUBLIC_BASE_URL", "https://ara.example.com/api"),
        ):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        source = json.loads(output)["sources"][0]
        self.assertEqual(
            source["metadata"]["url"],
            "https://ara.example.com/api/documents/doc-1/file#page=3",
        )
