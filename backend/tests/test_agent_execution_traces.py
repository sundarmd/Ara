import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from models.schemas import ChatRequest
from services.agent_orchestrator import AgentOrchestrator, _build_chat_history


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
