import threading
import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from langchain_core.documents import Document

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


class ResearchVectorStoreSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_runs_similarity_search_in_executor(self):
        loop_thread_id = threading.get_ident()

        class FakeVectorStore:
            def __init__(self):
                self.search_thread_id = None
                self.search_kwargs = None

            def similarity_search_with_score(self, query, k, filter):
                self.search_thread_id = threading.get_ident()
                self.search_kwargs = {
                    "query": query,
                    "k": k,
                    "filter": filter,
                }
                return [
                    (
                        Document(
                            id="chunk-1",
                            page_content="Duration should rally.",
                            metadata={"doc_id": "doc-1"},
                        ),
                        0.12,
                    )
                ]

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        results = await store.search(
            query="duration",
            n_results=3,
            filter_bank="GS",
            filter_asset_class="rates",
        )

        self.assertNotEqual(fake_vector_store.search_thread_id, loop_thread_id)
        self.assertEqual(
            fake_vector_store.search_kwargs,
            {
                "query": "duration",
                "k": 3,
                "filter": {"bank": "GS", "asset_class": "rates"},
            },
        )
        self.assertEqual(
            results,
            [
                {
                    "id": "chunk-1",
                    "text": "Duration should rally.",
                    "metadata": {"doc_id": "doc-1"},
                    "distance": 0.12,
                }
            ],
        )


class ResearchVectorStoreDeleteTests(unittest.TestCase):
    def test_delete_document_deletes_queried_ids_and_returns_count(self):
        class FakeVectorStore:
            def __init__(self):
                self.get_calls = 0
                self.where_calls = []
                self.deleted_ids = None

            def get(self, where):
                self.get_calls += 1
                self.where_calls.append(where)
                return {"ids": ["chunk-1", "chunk-2"] if self.get_calls == 1 else []}

            def delete(self, ids):
                self.deleted_ids = ids

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        deleted_count = store.delete_document("doc-1")

        self.assertEqual(deleted_count, 2)
        self.assertEqual(
            fake_vector_store.where_calls,
            [{"doc_id": "doc-1"}, {"doc_id": "doc-1"}],
        )
        self.assertEqual(fake_vector_store.deleted_ids, ["chunk-1", "chunk-2"])

    def test_delete_document_raises_when_verification_finds_remaining_ids(self):
        class FakeVectorStore:
            def __init__(self):
                self.get_calls = 0
                self.where_calls = []

            def get(self, where):
                self.get_calls += 1
                self.where_calls.append(where)
                return {"ids": ["chunk-1"]}

            def delete(self, ids):
                self.deleted_ids = ids

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        with self.assertRaises(RuntimeError) as raised:
            store.delete_document("doc-1")

        self.assertIn("Vector deletion verification failed", str(raised.exception))
        self.assertEqual(
            fake_vector_store.where_calls,
            [{"doc_id": "doc-1"}, {"doc_id": "doc-1"}],
        )
