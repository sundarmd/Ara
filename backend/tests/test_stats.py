import threading
import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException
from langchain_core.documents import Document

import main
from config.settings import settings
from models.schemas import Chunk
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
    def test_init_disables_chroma_telemetry(self):
        embedding_client = Mock()

        with (
            patch("services.database.os.makedirs"),
            patch("services.database.get_embedding_client", return_value=embedding_client),
            patch("services.database.Chroma") as chroma,
        ):
            ResearchVectorStore()

        kwargs = chroma.call_args.kwargs
        self.assertEqual(kwargs["collection_name"], "research_chunks")
        self.assertEqual(kwargs["embedding_function"], embedding_client)
        self.assertEqual(kwargs["persist_directory"], settings.VECTOR_DB_DIR)
        self.assertTrue(kwargs["client_settings"].is_persistent)
        self.assertFalse(kwargs["client_settings"].anonymized_telemetry)

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


class ResearchVectorStoreIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_index_chunks_includes_table_artifact_metadata(self):
        class FakeVectorStore:
            def __init__(self):
                self.documents = None

            def add_documents(self, documents):
                self.documents = documents

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        await store.index_chunks([
            Chunk(
                id="chunk-1",
                doc_id="doc-1",
                bank="BSH",
                asset_class="lab_data",
                report_date="2026-01-01",
                page_start=5,
                page_end=5,
                section="Measurement Results",
                segment_types=["table"],
                text="table excerpt",
                table_artifact_path="/data/tables/doc-1/page-5.md",
                table_row_start=10,
                table_row_end=20,
            )
        ])

        document = fake_vector_store.documents[0]
        self.assertEqual(document.metadata["table_artifact_path"], "/data/tables/doc-1/page-5.md")
        self.assertEqual(document.metadata["table_row_start"], 10)
        self.assertEqual(document.metadata["table_row_end"], 20)

    async def test_index_chunks_retries_rate_limit_errors(self):
        class FakeVectorStore:
            def __init__(self):
                self.calls = 0

            def add_documents(self, documents):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("429 Too Many Requests")
                self.documents = documents

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        with (
            patch.object(settings, "EMBEDDING_MAX_RETRIES", 1),
            patch.object(settings, "EMBEDDING_RETRY_BASE_SECONDS", 0.01),
            patch.object(settings, "EMBEDDING_RETRY_JITTER_SECONDS", 0),
            patch("services.database.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            await store.index_chunks([
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
                    text="Duration should rally.",
                )
            ])

        self.assertEqual(fake_vector_store.calls, 2)
        sleep.assert_awaited_once()


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
                "filter": {"$and": [{"bank": "GS"}, {"asset_class": "rates"}]},
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

    async def test_search_retries_rate_limit_errors(self):
        class FakeVectorStore:
            def __init__(self):
                self.calls = 0

            def similarity_search_with_score(self, query, k, filter):
                self.calls += 1
                if self.calls == 1:
                    raise RuntimeError("rate limit reached")
                return [
                    (
                        Document(
                            id="chunk-1",
                            page_content="Equities rallied.",
                            metadata={"doc_id": "doc-1"},
                        ),
                        0.2,
                    )
                ]

        fake_vector_store = FakeVectorStore()
        store = object.__new__(ResearchVectorStore)
        store.vectorstore = fake_vector_store

        with (
            patch.object(settings, "EMBEDDING_MAX_RETRIES", 1),
            patch.object(settings, "EMBEDDING_RETRY_BASE_SECONDS", 0.01),
            patch.object(settings, "EMBEDDING_RETRY_JITTER_SECONDS", 0),
            patch("services.database.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            results = await store.search(query="equities", n_results=1)

        self.assertEqual(fake_vector_store.calls, 2)
        self.assertEqual(results[0]["text"], "Equities rallied.")
        sleep.assert_awaited_once()


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
