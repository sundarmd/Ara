import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi import HTTPException

import main


class DebugSearchTests(unittest.IsolatedAsyncioTestCase):
    async def test_debug_search_passes_query_text_and_filters_to_vector_store(self):
        store = Mock()
        store.search = AsyncMock(return_value=[{"id": "chunk-1"}])

        with patch.object(main, "get_vector_store", return_value=store):
            response = await main.debug_search(
                q="EM assets",
                n_results=3,
                bank="GS",
                asset_class="multi_asset",
            )

        store.search.assert_awaited_once_with(
            query="EM assets",
            n_results=3,
            filter_bank="GS",
            filter_asset_class="multi_asset",
        )
        self.assertEqual(response["query"], "EM assets")
        self.assertEqual(response["n_results"], 1)
        self.assertEqual(response["results"], [{"id": "chunk-1"}])

    async def test_debug_search_wraps_vector_store_errors_as_http_500(self):
        store = Mock()
        store.search = AsyncMock(side_effect=RuntimeError("vector failed"))

        with patch.object(main, "get_vector_store", return_value=store):
            with self.assertRaises(HTTPException) as raised:
                await main.debug_search(q="EM assets")

        self.assertEqual(raised.exception.status_code, 500)
        self.assertIn("vector failed", raised.exception.detail)

