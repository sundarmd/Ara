import json
import unittest
from unittest.mock import AsyncMock, patch

from services import tools


class ToolOutputContractTests(unittest.IsolatedAsyncioTestCase):
    async def test_tool_errors_use_json_contract(self):
        with patch.object(
            tools,
            "search_documents",
            AsyncMock(side_effect=RuntimeError("vector failed")),
        ):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["sources"], [])
        self.assertEqual(payload["error"], "Error searching knowledge base: vector failed")
