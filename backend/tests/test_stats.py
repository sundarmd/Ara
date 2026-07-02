import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

import main
from config.settings import settings
from services.database import ResearchVectorStore


class StatsEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_stats_returns_vector_store_collection_stats(self):
        expected_stats = {
            "collection_name": "research_chunks",
            "document_count": 7,
            "persist_directory": "/app/data/vector_store",
        }
        store = Mock()
        store.get_collection_stats.return_value = expected_stats

        with patch.object(main, "get_vector_store", return_value=store):
            response = await main.get_stats()

        store.get_collection_stats.assert_called_once_with()
        self.assertEqual(response, expected_stats)

    async def test_get_stats_wraps_vector_store_errors_as_http_500(self):
        store = Mock()
        store.get_collection_stats.side_effect = RuntimeError("stats failed")

        with patch.object(main, "get_vector_store", return_value=store):
            with self.assertRaises(HTTPException) as raised:
                await main.get_stats()

        self.assertEqual(raised.exception.status_code, 500)
        self.assertIn("stats failed", raised.exception.detail)


class ResearchVectorStoreStatsTests(unittest.TestCase):
    def test_get_collection_stats_counts_chroma_collection(self):
        collection = Mock()
        collection.count.return_value = 7
        vector_store = Mock()
        vector_store._collection = collection

        store = object.__new__(ResearchVectorStore)
        store.vectorstore = vector_store

        self.assertEqual(
            store.get_collection_stats(),
            {
                "collection_name": "research_chunks",
                "document_count": 7,
                "persist_directory": settings.VECTOR_DB_DIR,
            },
        )
        collection.count.assert_called_once_with()

    def test_get_collection_stats_handles_missing_collection(self):
        vector_store = Mock()
        vector_store._collection = None

        store = object.__new__(ResearchVectorStore)
        store.vectorstore = vector_store

        self.assertEqual(
            store.get_collection_stats(),
            {
                "collection_name": "research_chunks",
                "document_count": 0,
                "persist_directory": settings.VECTOR_DB_DIR,
            },
        )

