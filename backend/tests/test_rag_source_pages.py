import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from services import tools


class RagSourcePageTests(unittest.IsolatedAsyncioTestCase):
    async def test_knowledge_base_source_preserves_page_range(self):
        search_results = [
            {
                "text": "A multi-page report chunk",
                "metadata": {
                    "doc_id": "doc-1",
                    "page_start": 5,
                    "page_end": 7,
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

        source = json.loads(output)["sources"][0]
        self.assertEqual(source["metadata"]["page_start"], 5)
        self.assertEqual(source["metadata"]["page_end"], 7)
        self.assertTrue(
            source["metadata"]["url"].endswith("/documents/doc-1/file#page=5"),
            source["metadata"]["url"],
        )
