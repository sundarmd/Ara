import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from services import tools


class RagSourceTitleTests(unittest.IsolatedAsyncioTestCase):
    async def test_knowledge_base_source_title_uses_document_store_title(self):
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
            title="Global Market Views",
            filename="goldman-global-market-views.pdf",
        )

        with (
            patch.object(tools, "search_documents", AsyncMock(return_value=search_results)),
            patch.object(tools, "get_document_store", return_value=doc_store),
        ):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        source = json.loads(output)[0]
        self.assertEqual(source["metadata"]["title"], "Global Market Views")
        doc_store.get_document.assert_called_once_with("doc-1")

    async def test_knowledge_base_source_title_falls_back_to_document_filename(self):
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
            title=None,
            filename="goldman-global-market-views.pdf",
        )

        with (
            patch.object(tools, "search_documents", AsyncMock(return_value=search_results)),
            patch.object(tools, "get_document_store", return_value=doc_store),
        ):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        source = json.loads(output)[0]
        self.assertEqual(source["metadata"]["title"], "goldman-global-market-views.pdf")

