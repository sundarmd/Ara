import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from models.schemas import ChatRequest, Recommendation
from services.agent_orchestrator import (
    AgentOrchestrator,
    _build_chat_history,
    _build_system_prompt,
    _wants_structured_recommendations,
)


def parse_sse(event_line):
    return json.loads(event_line.removeprefix("data: "))


class AgentChatHistoryTests(unittest.TestCase):
    def test_build_chat_history_uses_prior_user_and_assistant_turns(self):
        request = ChatRequest(
            messages=[
                {"role": "system", "content": "System instruction"},
                {"role": "user", "content": "First question"},
                {"role": "assistant", "content": "First answer"},
                {"role": "user", "content": "Follow-up question"},
            ],
        )

        self.assertEqual(
            _build_chat_history(request.messages),
            [
                ("human", "First question"),
                ("ai", "First answer"),
            ],
        )

    def test_build_system_prompt_includes_current_date_guidance(self):
        with patch("services.agent_orchestrator._today_iso", return_value="2026-07-07"):
            prompt = _build_system_prompt("Base prompt.")

        self.assertIn("Today is 2026-07-07", prompt)
        self.assertIn("use web_search", prompt)


class RecommendationIntentTests(unittest.TestCase):
    def test_detects_alternate_recommendation_phrasings(self):
        queries = [
            "List stances from the indexed research.",
            "What are the calls across asset classes?",
            "Show investment views from the extracted reports.",
            "Which assets are overweight or underweight?",
            "Show the structured view extracted from the research.",
        ]

        for query in queries:
            with self.subTest(query=query):
                self.assertTrue(_wants_structured_recommendations(query))

    def test_does_not_match_generic_view_questions(self):
        self.assertFalse(
            _wants_structured_recommendations("What is the current view on duration?")
        )


class AgentExecutionTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestrator_emits_code_owned_tool_traces(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_tool_start",
                    "name": "search_knowledge_base",
                    "data": {"input": {"query": "duration views"}},
                }
                yield {
                    "event": "on_tool_end",
                    "name": "search_knowledge_base",
                    "data": {
                        "output": json.dumps([
                            {
                                "text": "Duration view",
                                "metadata": {"citation_id": 1},
                            }
                        ])
                    },
                }
                yield {
                    "event": "on_chat_model_stream",
                    "data": {
                        "chunk": SimpleNamespace(
                            content="<thought>hidden reasoning</thought>Visible answer "
                        )
                    },
                }
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {
                        "output": {
                            "output": "<thought>hidden final</thought>Final answer [1]"
                        }
                    },
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        request = ChatRequest(
            messages=[{"role": "user", "content": "What are duration views?"}],
        )
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 1.0

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        thought_events = [event for event in events if event["type"] == "thought"]
        token_events = [event for event in events if event["type"] == "token"]
        complete_event = [event for event in events if event["type"] == "complete"][0]

        self.assertIn("Searching Research Report Knowledge Base", thought_events[0]["content"])
        self.assertIn("Found 1 source", thought_events[1]["content"])
        self.assertEqual(thought_events[-1]["content"], "Synthesizing answer.")
        self.assertEqual(token_events[0]["content"], "Visible answer ")
        self.assertEqual(complete_event["answer"], "Final answer [1]")
        serialized_events = json.dumps(events)
        self.assertNotIn("hidden reasoning", serialized_events)
        self.assertNotIn("hidden final", serialized_events)

    async def test_orchestrator_surfaces_structured_tool_errors(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_tool_end",
                    "name": "search_knowledge_base",
                    "data": {
                        "output": json.dumps({
                            "ok": False,
                            "error": "vector store unavailable",
                            "sources": [],
                        })
                    },
                }
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "I could not search the reports."}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        request = ChatRequest(
            messages=[{"role": "user", "content": "What are duration views?"}],
        )
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 1.0

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        error_trace = [
            event for event in events
            if event["type"] == "thought" and "returned an error" in event["content"]
        ][0]
        complete_event = [event for event in events if event["type"] == "complete"][0]

        self.assertEqual(error_trace["details"][0]["error"], "vector store unavailable")
        self.assertEqual(error_trace["details"][0]["source_count"], 0)
        self.assertEqual(complete_event["sources"], [])

    async def test_orchestrator_adds_fallback_sources_when_answer_has_none(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "Investment themes are broad."}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        fallback_output = json.dumps({
            "ok": True,
            "sources": [
                {
                    "citation_id": 1,
                    "text": "Investment advice should consider objectives and risk tolerance.",
                    "metadata": {"title": "SEC Exam Priorities", "page_start": 9},
                }
            ],
        })
        fallback_tool = Mock()
        fallback_tool.ainvoke = AsyncMock(return_value=fallback_output)

        request = ChatRequest(
            messages=[{"role": "user", "content": "Summarize the uploaded reports and cite pages."}],
        )

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
            patch("services.agent_orchestrator.search_knowledge_base", fallback_tool),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        complete_event = [event for event in events if event["type"] == "complete"][0]
        self.assertEqual(len(complete_event["sources"]), 1)
        self.assertIn("[1]", complete_event["answer"])
        fallback_tool.ainvoke.assert_awaited_once()

    async def test_orchestrator_returns_cited_fallback_on_rate_limit(self):
        class RateLimitError(Exception):
            pass

        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                raise RateLimitError("429 rate limit exceeded")
                yield

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        fallback_output = json.dumps({
            "ok": True,
            "sources": [
                {
                    "citation_id": 1,
                    "text": "Fund mergers can affect investor fees.",
                    "metadata": {"title": "When Funds Merge", "page_start": 1},
                }
            ],
        })
        fallback_tool = Mock()
        fallback_tool.ainvoke = AsyncMock(return_value=fallback_output)

        request = ChatRequest(
            messages=[{"role": "user", "content": "What do the uploaded PDFs say about fund fees?"}],
        )

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
            patch("services.agent_orchestrator.search_knowledge_base", fallback_tool),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        complete_event = [event for event in events if event["type"] == "complete"][0]
        error_events = [event for event in events if event["type"] == "error"]
        self.assertEqual(error_events, [])
        self.assertEqual(len(complete_event["sources"]), 1)
        self.assertIn("provider rate limit", complete_event["answer"])
        self.assertIn("[1]", complete_event["answer"])

    async def test_orchestrator_includes_stored_recommendations_for_recommendation_queries(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "Here are the structured recommendations."}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()
        recommendation_store = Mock()
        recommendation_store.get_by_filters = AsyncMock(return_value=[
            Recommendation(
                id="rec-1",
                doc_id="doc-1",
                bank="GS",
                source_type="sell_side",
                asset_class="rates",
                sub_asset="US duration",
                stance="Long",
                horizon="3m",
                rationale="Soft landing supports duration.",
                page=4,
                section="Duration",
                confidence="high",
                date="2026-01-01",
            )
        ])

        request = ChatRequest(
            messages=[{
                "role": "user",
                "content": "List the structured recommendations from the indexed research and include stance, asset class, and rationale.",
            }],
            bank="GS",
            asset_class="rates",
        )

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
            patch("services.recommendations.get_recommendation_store", return_value=recommendation_store),
            patch.object(orchestrator, "_load_fallback_sources", new=AsyncMock(return_value=[])),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        complete_event = [event for event in events if event["type"] == "complete"][0]
        recommendations = complete_event["recommendations"]

        recommendation_store.get_by_filters.assert_awaited_once_with(
            bank="GS",
            asset_class="rates",
            source_type="sell_side",
            is_active=True,
        )
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]["asset_class"], "rates")
        self.assertEqual(recommendations[0]["stance"], "Long")
        self.assertEqual(recommendations[0]["rationale"], "Soft landing supports duration.")
        self.assertEqual(recommendations[0]["page"], 4)
        self.assertEqual(recommendations[0]["section"], "Duration")

    async def test_orchestrator_does_not_load_recommendations_for_general_queries(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "Duration views are constructive."}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()
        recommendation_store = Mock()
        recommendation_store.get_by_filters = AsyncMock(return_value=[])

        request = ChatRequest(
            messages=[{"role": "user", "content": "What is the current view on duration?"}],
        )

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
            patch("services.recommendations.get_recommendation_store", return_value=recommendation_store),
            patch.object(orchestrator, "_load_fallback_sources", new=AsyncMock(return_value=[])),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        complete_event = [event for event in events if event["type"] == "complete"][0]

        recommendation_store.get_by_filters.assert_not_called()
        self.assertEqual(complete_event["recommendations"], [])

    async def test_orchestrator_does_not_load_recommendations_for_generic_structured_queries(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                yield {
                    "event": "on_chain_end",
                    "name": "AgentExecutor",
                    "data": {"output": {"output": "Here is a structured summary."}},
                }

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()
        recommendation_store = Mock()
        recommendation_store.get_by_filters = AsyncMock(return_value=[])

        request = ChatRequest(
            messages=[{"role": "user", "content": "Give me a structured summary of the report metadata."}],
        )

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
            patch("services.recommendations.get_recommendation_store", return_value=recommendation_store),
            patch.object(orchestrator, "_load_fallback_sources", new=AsyncMock(return_value=[])),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        complete_event = [event for event in events if event["type"] == "complete"][0]

        recommendation_store.get_by_filters.assert_not_called()
        self.assertEqual(complete_event["recommendations"], [])

    async def test_orchestrator_emits_typed_chat_errors(self):
        class FakeAgentExecutor:
            def __init__(self, agent, tools, verbose):
                pass

            async def astream_events(self, payload, version):
                raise RuntimeError("chat provider failed")
                yield

        orchestrator = object.__new__(AgentOrchestrator)
        orchestrator.llm = Mock()

        request = ChatRequest(
            messages=[{"role": "user", "content": "What are duration views?"}],
        )
        loop = asyncio.get_running_loop()
        loop.slow_callback_duration = 1.0

        with (
            patch("langchain.agents.create_tool_calling_agent", return_value=Mock()),
            patch("langchain.agents.AgentExecutor", FakeAgentExecutor),
        ):
            events = [parse_sse(event) async for event in orchestrator.process_query(request)]

        error_event = [event for event in events if event["type"] == "error"][0]
        self.assertEqual(error_event["code"], "chat_error")
        self.assertEqual(
            error_event["message"],
            "I encountered an error processing your request: chat provider failed",
        )
