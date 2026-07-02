import asyncio
import json
import unittest
from unittest.mock import AsyncMock, Mock, patch

from models.schemas import ChatRequest
from services import tools
from services.agent_orchestrator import AgentOrchestrator


class ChatFilterToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_search_knowledge_base_passes_explicit_filters_to_search_documents(self):
        search_documents = AsyncMock(return_value=[])

        with (
            patch.object(tools.settings, "RAG_SEARCH_RESULTS", 7),
            patch.object(tools, "search_documents", search_documents),
        ):
            output = await tools.search_knowledge_base.ainvoke(
                {
                    "query": "duration views",
                    "bank": "GS",
                    "asset_class": "fixed_income",
                }
            )

        payload = json.loads(output)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["sources"], [])
        self.assertEqual(payload["message"], "No relevant information found in knowledge base.")
        search_documents.assert_awaited_once_with(
            query="duration views",
            n_results=7,
            filter_bank="GS",
            filter_asset_class="fixed_income",
        )

    async def test_request_filter_scope_overrides_tool_filters(self):
        search_documents = AsyncMock(return_value=[])
        token = tools.set_search_filter_scope(bank="UBS", asset_class="multi_asset")

        try:
            with (
                patch.object(tools.settings, "RAG_SEARCH_RESULTS", 6),
                patch.object(tools, "search_documents", search_documents),
            ):
                await tools.search_knowledge_base.ainvoke(
                    {
                        "query": "duration views",
                        "bank": "GS",
                        "asset_class": "fixed_income",
                    }
                )
        finally:
            tools.reset_search_filter_scope(token)

        search_documents.assert_awaited_once_with(
            query="duration views",
            n_results=6,
            filter_bank="UBS",
            filter_asset_class="multi_asset",
        )

    async def test_orchestrator_applies_chat_request_filters_during_tool_execution(self):
        search_documents = AsyncMock(return_value=[])

        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                await tools.search_knowledge_base.coroutine(query="duration views")
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "done"}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        request = ChatRequest(
            messages=[{"role": "user", "content": "What does the report say?"}],
            bank="GS",
            asset_class="fixed_income",
        )

        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 1.0

        with (
            patch.object(tools.settings, "RAG_SEARCH_RESULTS", 5),
            patch.object(tools, "search_documents", search_documents),
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
        ):
            events = [event async for event in orchestrator.process_query(request)]

        parsed_events = [json.loads(event.removeprefix("data: ")) for event in events]
        complete_event = [event for event in parsed_events if event["type"] == "complete"][0]
        self.assertEqual(complete_event["answer"], "done")
        search_documents.assert_awaited_once_with(
            query="duration views",
            n_results=5,
            filter_bank="GS",
            filter_asset_class="fixed_income",
        )
