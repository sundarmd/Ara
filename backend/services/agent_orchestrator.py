"""
Agent orchestrator using LangChain and Mistral.

This module handles:
- Tool-calling workflow for query interpretation
- Tool selection and execution (RAG, SQL, Web) using LangChain
- Response generation with code-owned execution traces
"""
import logging
import json
import re
from datetime import date
from typing import Optional, Dict, Any, AsyncGenerator, List, Tuple

from langchain_openai import ChatOpenAI

from config.settings import settings
from services.errors import format_chat_error
from services.tools import (
    AVAILABLE_TOOLS,
    reset_search_filter_scope,
    search_knowledge_base,
    set_search_filter_scope,
    web_search,
)
from models.schemas import ChatMessage, ChatRequest, StreamEventType

logger = logging.getLogger(__name__)

TOOL_DISPLAY_NAMES = {
    "query_internal_views": "Internal Investment Database",
    "get_analyst_intelligence": "Analyst Intelligence",
    "search_knowledge_base": "Research Report Knowledge Base",
    "web_search": "Live Web Search",
}
MAX_CHAT_RECOMMENDATIONS = 20
STRUCTURED_RECOMMENDATION_QUERY_MARKERS = (
    "recommendation",
    "recommendations",
    "asset allocation",
    "trade idea",
    "trade ideas",
    "stance",
    "stances",
    "overweight",
    "underweight",
    "investment view",
    "investment views",
    "structured recommendation",
    "structured recommendations",
    "structured view",
    "structured views",
    "calls",
)
WEB_QUERY_MARKERS = (
    "latest",
    "current",
    "today",
    "live",
    "web",
    "news",
    "headline",
    "headlines",
    "market headlines",
)
CITED_FALLBACK_QUERY_MARKERS = (
    "cite",
    "citation",
    "citations",
    "source",
    "sources",
    "page",
    "pages",
    "uploaded",
    "document",
    "documents",
    "pdf",
    "pdfs",
    "report",
    "reports",
)


def _has_query_marker(query: str, marker: str) -> bool:
    if " " in marker:
        return marker in query
    return re.search(rf"\b{re.escape(marker)}\b", query) is not None


def _wants_structured_recommendations(query: str) -> bool:
    """Return True only for queries asking for structured recommendation data."""
    normalized = query.lower()
    return any(
        _has_query_marker(normalized, marker)
        for marker in STRUCTURED_RECOMMENDATION_QUERY_MARKERS
    )


def _wants_web_search(query: str) -> bool:
    normalized = query.lower()
    return any(_has_query_marker(normalized, marker) for marker in WEB_QUERY_MARKERS)


def _needs_cited_fallback(query: str) -> bool:
    normalized = query.lower()
    return _wants_web_search(query) or any(
        _has_query_marker(normalized, marker)
        for marker in CITED_FALLBACK_QUERY_MARKERS
    )


def _looks_like_rate_limit_error(error: Exception) -> bool:
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if status_code == 429:
        return True

    message = str(error).lower()
    return "429" in message or "rate limit" in message or "too many requests" in message


def _build_chat_history(messages: List[ChatMessage]) -> List[Tuple[str, str]]:
    """Convert prior chat turns into LangChain's prompt placeholder tuple format."""
    history = []
    for message in messages[:-1]:
        if message.role == "user":
            history.append(("human", message.content))
        elif message.role == "assistant":
            history.append(("ai", message.content))
    return history


def _today_iso() -> str:
    return date.today().isoformat()


def _build_system_prompt(base_prompt: str) -> str:
    today_iso = _today_iso()
    return (
        f"{base_prompt.rstrip()}\n\n"
        "# CURRENT DATE\n"
        f"Today is {today_iso}. For queries that mention today, latest, current, "
        "recent, live, or breaking market context, use web_search and keep the "
        "answer scoped to sources returned for that date-aware search."
    )


class AgentOrchestrator:
    """
    Tool-calling orchestrator using LangChain + Mistral (via OpenAI Adapter) for planning and execution.
    """
    
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.endpoint = settings.MISTRAL_CHAT_ENDPOINT
        self.model_name = settings.MISTRAL_CHAT_MODEL
        
        # Initialize LangChain OpenAI Adapter pointing to Mistral
        # Mistral API is OpenAI compatible
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            base_url="https://api.mistral.ai/v1",
            model=self.model_name,
            temperature=0,
            max_retries=settings.CHAT_MAX_RETRIES,
            stop=[
                "\nSources:", 
                "\nReferences:", 
                "\n**Sources", 
                "\n**References", 
                "\n# Sources", 
                "\n# References"
            ]
        )
    
    async def process_query(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """
        Process a user query using LangChain's AgentExecutor.
        Yields SSE events: thought, token, complete, error.
        """
        search_filter_token = None
        input_text = request.messages[-1].content if request.messages else ""
        
        try:
            from langchain.agents import AgentExecutor, create_tool_calling_agent
            from langchain_core.prompts import ChatPromptTemplate
            from services.prompt_loader import load_prompt
            
            # Load system prompt from markdown file
            system_prompt = _build_system_prompt(load_prompt("agent_system"))
            
            # Define prompt for tool-calling execution.
            prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                ("placeholder", "{chat_history}"),
                ("human", "{input}"),
                ("placeholder", "{agent_scratchpad}"),
            ])
            
            # Create Agent
            agent = create_tool_calling_agent(self.llm, AVAILABLE_TOOLS, prompt)
            agent_executor = AgentExecutor(agent=agent, tools=AVAILABLE_TOOLS, verbose=True)

            # Execute with streaming
            history = _build_chat_history(request.messages)
            
            # Streaming state
            collected_sources = []
            tools_used = []
            tool_source_counts = {}

            yield self._format_event(StreamEventType.THOUGHT, {
                "phase": "analyzing",
                "content": self._build_request_trace(request, input_text),
                "details": [{
                    "history_messages": max(0, len(request.messages) - 1),
                    "query_length": len(input_text),
                }],
            })
            yield self._format_event(StreamEventType.THOUGHT, {
                "phase": "analyzing",
                "content": self._build_route_trace(input_text),
                "details": [{
                    "needs_web": int(_wants_web_search(input_text)),
                    "needs_recommendations": int(_wants_structured_recommendations(input_text)),
                    "needs_citations": int(_needs_cited_fallback(input_text)),
                }],
            })

            search_filter_token = set_search_filter_scope(
                bank=request.bank,
                asset_class=request.asset_class,
            )
            yield self._format_event(StreamEventType.THOUGHT, {
                "phase": "searching",
                "content": self._build_filter_trace(request),
                "details": [{
                    "bank": request.bank,
                    "asset_class": request.asset_class,
                }],
            })
            yield self._format_event(StreamEventType.THOUGHT, {
                "phase": "analyzing",
                "content": self._build_execution_plan_trace(request, input_text),
                "details": [{
                    "needs_web": _wants_web_search(input_text),
                    "needs_recommendations": _wants_structured_recommendations(input_text),
                    "needs_citations": _needs_cited_fallback(input_text),
                }],
            })
            
            async for event in agent_executor.astream_events(
                {"input": input_text, "chat_history": history},
                version="v1"
            ):
                kind = event["event"]
                
                if kind == "on_chat_model_stream":
                    # ... (Existing stream logic) ...
                    chunk = event["data"]["chunk"]
                    content = self._coerce_model_text(chunk.content)
                        
                    if content:
                        visible_content = self._strip_private_markup(content)
                        if visible_content:
                            yield self._format_event(StreamEventType.TOKEN, {
                                "content": visible_content
                            })

                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    tool_input = event["data"].get("input", {})
                    tools_used.append(tool_name)
                    thought_content = self._build_tool_start_trace(tool_name, tool_input)
                        
                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "searching",
                        "content": thought_content,
                        "details": [{"tool": tool_name, "args": json.dumps(tool_input)}]
                    })
                
                elif kind == "on_tool_end":
                    # Parse output for sources
                    tool_name = event["name"]
                    output = event["data"].get("output")
                    parsed_sources, tool_error = self._parse_tool_output(output)
                    collected_sources.extend(parsed_sources)
                    source_count = len(parsed_sources)
                    tool_source_counts[tool_name] = (
                        tool_source_counts.get(tool_name, 0) + source_count
                    )
                    details = {"tool": tool_name, "source_count": source_count}
                    if tool_error:
                        details["error"] = tool_error

                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "analyzing",
                        "content": self._build_tool_error_trace(tool_name, tool_error)
                        if tool_error
                        else self._build_tool_end_trace(tool_name, source_count),
                        "details": [details]
                    })
                    if parsed_sources:
                        yield self._format_event(StreamEventType.THOUGHT, {
                            "phase": "analyzing",
                            "content": self._build_source_summary_trace(
                                tool_name,
                                parsed_sources,
                            ),
                            "details": [{
                                "tool": tool_name,
                                "source_count": source_count,
                            }],
                        })
                        yield self._format_event(StreamEventType.THOUGHT, {
                            "phase": "analyzing",
                            "content": self._build_evidence_coverage_trace(
                                tool_name,
                                parsed_sources,
                            ),
                            "details": [{
                                "tool": tool_name,
                                "source_count": source_count,
                                "document_count": len(self._source_document_keys(parsed_sources)),
                            }],
                        })

                elif kind == "on_chain_end" and event["name"] == "AgentExecutor":
                    result = event["data"].get("output")
                    if result and isinstance(result, dict) and "output" in result:
                        final_answer = self._coerce_model_text(result["output"])
                        clean_answer = self._strip_private_markup(final_answer).strip()

                        recommendations = await self._load_structured_recommendations(
                            request=request,
                            query=input_text,
                        )
                        yield self._format_event(StreamEventType.THOUGHT, {
                            "phase": "analyzing",
                            "content": self._build_recommendation_trace(
                                query=input_text,
                                recommendations=recommendations,
                            ),
                            "details": [{
                                "recommendation_count": len(recommendations),
                            }],
                        })
                        if not collected_sources and _needs_cited_fallback(input_text):
                            fallback_sources = await self._load_fallback_sources(
                                request=request,
                                query=input_text,
                            )
                            if fallback_sources:
                                collected_sources.extend(fallback_sources)
                                clean_answer = self._ensure_answer_has_citation(
                                    clean_answer,
                                    collected_sources,
                                )
                                yield self._format_event(StreamEventType.THOUGHT, {
                                    "phase": "analyzing",
                                    "content": self._build_source_summary_trace(
                                        "fallback",
                                        fallback_sources,
                                    ),
                                    "details": [{
                                        "tool": "fallback",
                                        "source_count": len(fallback_sources),
                                    }],
                                })
                                yield self._format_event(StreamEventType.THOUGHT, {
                                    "phase": "analyzing",
                                    "content": self._build_evidence_coverage_trace(
                                        "fallback",
                                        fallback_sources,
                                    ),
                                    "details": [{
                                        "tool": "fallback",
                                        "source_count": len(fallback_sources),
                                        "document_count": len(self._source_document_keys(fallback_sources)),
                                    }],
                                })

                        yield self._format_event(StreamEventType.THOUGHT, {
                            "phase": "generating",
                            "content": self._build_synthesis_trace(
                                sources=collected_sources,
                                tools_used=tools_used,
                                tool_source_counts=tool_source_counts,
                            ),
                            "details": [{
                                "source_count": len(collected_sources),
                                "tool_count": len(tools_used),
                            }],
                        })

                        yield self._format_event(StreamEventType.COMPLETE, {
                            "answer": clean_answer,
                            "sources": collected_sources,
                            "recommendations": recommendations,
                        })
            
        except Exception as e:
            logger.error(f"LangChain Orchestrator error: {e}", exc_info=True)
            if _looks_like_rate_limit_error(e) and _needs_cited_fallback(input_text):
                fallback_sources = await self._load_fallback_sources(
                    request=request,
                    query=input_text,
                )
                if fallback_sources:
                    yield self._format_event(StreamEventType.THOUGHT, {
                        "phase": "generating",
                        "content": "Using cited fallback after provider rate limit."
                    })
                    yield self._format_event(StreamEventType.COMPLETE, {
                        "answer": self._build_rate_limit_fallback_answer(fallback_sources),
                        "sources": fallback_sources,
                        "recommendations": await self._load_structured_recommendations(
                            request=request,
                            query=input_text,
                        ),
                    })
                    return

            error_message = format_chat_error(e)
            yield self._format_event(StreamEventType.ERROR, {
                "message": error_message,
                "code": "chat_error",
            })
        finally:
            if search_filter_token is not None:
                reset_search_filter_scope(search_filter_token)
                    


    def _format_event(self, event_type: str, data: Dict[str, Any]) -> str:
        """Format data as SSE string."""
        return f"data: {json.dumps({'type': event_type, **data})}\n\n"

    def _strip_private_markup(self, content: str) -> str:
        """Remove private/planning markup if a model emits it despite the prompt."""
        content = re.sub(
            r"<thought>.*?</thought>",
            "",
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )
        content = re.sub(r"</?thought>", "", content, flags=re.IGNORECASE)
        content = re.sub(r"<function.*?>", "", content, flags=re.DOTALL | re.IGNORECASE)
        return content

    def _coerce_model_text(self, content: Any) -> str:
        """Extract visible text from provider stream chunks without stringifying metadata blocks."""
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                    continue
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
                else:
                    text = getattr(item, "text", None)
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

        return str(content) if content is not None else ""

    def _parse_tool_output(self, output: Any) -> tuple[list[Dict[str, Any]], Optional[str]]:
        """Extract sources and tool errors from the shared tool-output contract."""
        if not output:
            return [], None

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            return [], str(output)

        if isinstance(data, list):
            return self._extract_source_items(data), None

        if isinstance(data, dict):
            sources = self._extract_source_items(data.get("sources", []))
            if data.get("ok") is False:
                return sources, data.get("error") or "Tool failed."
            return sources, None

        return [], "Tool returned unexpected output shape."

    def _extract_source_items(self, items: Any) -> list[Dict[str, Any]]:
        if not isinstance(items, list):
            return []
        return [
            item
            for item in items
            if isinstance(item, dict) and "metadata" in item
        ]

    async def _load_structured_recommendations(
        self,
        request: ChatRequest,
        query: str,
    ) -> list[Dict[str, Any]]:
        if not _wants_structured_recommendations(query):
            return []

        try:
            from services.recommendations import get_recommendation_store

            store = get_recommendation_store()
            recommendations = await store.get_by_filters(
                bank=request.bank,
                asset_class=request.asset_class,
                source_type="sell_side",
                is_active=True,
            )
        except Exception:
            logger.warning("Failed to load structured recommendations for chat", exc_info=True)
            return []

        return [
            recommendation.model_dump(exclude_none=True)
            for recommendation in recommendations[:MAX_CHAT_RECOMMENDATIONS]
        ]

    async def _load_fallback_sources(
        self,
        request: ChatRequest,
        query: str,
    ) -> list[Dict[str, Any]]:
        try:
            if _wants_web_search(query):
                output = await web_search.ainvoke({"query": query})
            else:
                output = await search_knowledge_base.ainvoke({
                    "query": query,
                    "bank": request.bank,
                    "asset_class": request.asset_class,
                })
        except Exception:
            logger.warning("Fallback source retrieval failed", exc_info=True)
            return []

        sources, tool_error = self._parse_tool_output(output)
        if tool_error:
            logger.warning("Fallback source retrieval returned error: %s", tool_error)
        return sources

    def _ensure_answer_has_citation(
        self,
        answer: str,
        sources: list[Dict[str, Any]],
    ) -> str:
        if re.search(r"\[\d+(?:\s*,\s*\d+)*\]", answer):
            return answer

        citation_ids = [
            source.get("citation_id")
            for source in sources
            if isinstance(source.get("citation_id"), int)
        ]
        if not citation_ids:
            return answer

        citations = " ".join(f"[{citation_id}]" for citation_id in citation_ids[:3])
        return f"{answer.rstrip()}\n\nRelevant retrieved evidence: {citations}"

    def _build_rate_limit_fallback_answer(self, sources: list[Dict[str, Any]]) -> str:
        lines = [
            "I hit a provider rate limit during synthesis, so I am returning the most relevant cited evidence directly."
        ]

        for source in sources[:5]:
            citation_id = source.get("citation_id")
            metadata = source.get("metadata") or {}
            title = metadata.get("title") or metadata.get("bank") or "Source"
            page = metadata.get("page_start")
            text = " ".join(str(source.get("text") or "").split())
            if len(text) > 260:
                text = f"{text[:257]}..."

            location = f", page {page}" if page else ""
            lines.append(f"- **{title}{location}:** {text} [{citation_id}]")

        return "\n".join(lines)

    def _build_request_trace(self, request: ChatRequest, query: str) -> str:
        history_count = max(0, len(request.messages) - 1)
        if history_count:
            history_part = f"Preserving {history_count} prior chat turn(s) for context"
        else:
            history_part = "Starting a new chat turn"

        query_preview = " ".join(query.split())
        if len(query_preview) > 180:
            query_preview = f"{query_preview[:177]}..."

        return (
            f"{history_part}. Reading the request and preparing an evidence-first "
            f"answer plan for: '{query_preview}'."
        )

    def _build_route_trace(self, query: str) -> str:
        route_notes = []
        if _wants_web_search(query):
            route_notes.append("live web search for current market context")
        if _wants_structured_recommendations(query):
            route_notes.append("structured recommendation lookup")
        if _needs_cited_fallback(query):
            route_notes.append("source-backed retrieval with citations")
        if not route_notes:
            route_notes.append("general report retrieval and synthesis")

        return "Routing the request through: " + "; ".join(route_notes) + "."

    def _build_filter_trace(self, request: ChatRequest) -> str:
        filters = []
        if request.bank:
            filters.append(f"bank={request.bank}")
        if request.asset_class:
            filters.append(f"asset_class={request.asset_class}")

        if filters:
            return "Applying chat-level filters before tool execution: " + ", ".join(filters) + "."
        return "No chat-level bank or asset-class filter is set; tools can search across all indexed sources."

    def _build_execution_plan_trace(self, request: ChatRequest, query: str) -> str:
        steps = [
            "preserve relevant chat context",
            "retrieve source-backed evidence before answering",
            "carry citation IDs, page numbers, sections, and titles into the response",
        ]

        if request.bank or request.asset_class:
            steps.append("keep user-selected filters scoped to retrieval")
        if _wants_web_search(query):
            steps.append("use live web search only for current or latest context")
        if _wants_structured_recommendations(query):
            steps.append("load structured recommendation rows for the response payload")
        if _needs_cited_fallback(query):
            steps.append("fall back to cited retrieval if synthesis returns no sources")

        return "Execution plan: " + "; ".join(steps) + "."

    def _build_source_summary_trace(
        self,
        tool_name: str,
        sources: list[Dict[str, Any]],
    ) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        labels = [self._format_source_label(source) for source in sources[:3]]
        labels = [label for label in labels if label]
        if not labels:
            return f"Inspecting {len(sources)} source(s) returned by {display_name}."

        suffix = ""
        if len(sources) > len(labels):
            suffix = f" plus {len(sources) - len(labels)} more"
        return (
            f"Inspecting evidence from {display_name}: "
            + "; ".join(labels)
            + suffix
            + "."
        )

    def _build_evidence_coverage_trace(
        self,
        tool_name: str,
        sources: list[Dict[str, Any]],
    ) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        document_count = len(self._source_document_keys(sources))
        page_ranges = self._source_page_ranges(sources)
        sections = self._source_sections(sources)
        citation_ids = self._source_citation_ids(sources)

        coverage_parts = [
            f"{self._count_phrase(len(sources), 'cited chunk')} across "
            f"{self._count_phrase(document_count, 'document')}"
        ]
        if page_ranges:
            coverage_parts.append("page coverage: " + ", ".join(page_ranges[:6]))
        if sections:
            coverage_parts.append("sections: " + ", ".join(sections[:4]))
        if citation_ids:
            citations = ", ".join(f"[{citation_id}]" for citation_id in citation_ids[:8])
            if len(citation_ids) > 8:
                citations += f", plus {len(citation_ids) - 8} more"
            coverage_parts.append("citations queued: " + citations)

        return "Evidence coverage from " + display_name + ": " + "; ".join(coverage_parts) + "."

    def _format_source_label(self, source: Dict[str, Any]) -> str:
        citation_id = source.get("citation_id")
        metadata = source.get("metadata") or {}
        title = metadata.get("title") or metadata.get("bank") or "Source"
        page_start = metadata.get("page_start")
        page_end = metadata.get("page_end")

        location = ""
        if page_start and page_end and page_end != page_start:
            location = f", pages {page_start}-{page_end}"
        elif page_start:
            location = f", page {page_start}"

        citation = f"[{citation_id}]" if citation_id is not None else ""
        return f"{title}{location} {citation}".strip()

    def _source_document_keys(self, sources: list[Dict[str, Any]]) -> list[str]:
        document_keys = []
        seen = set()
        for index, source in enumerate(sources):
            metadata = source.get("metadata") or {}
            citation_id = source.get("citation_id") or metadata.get("citation_id")
            key = (
                metadata.get("doc_id")
                or metadata.get("document_id")
                or metadata.get("title")
                or metadata.get("bank")
                or metadata.get("url")
                or f"source:{citation_id or index}"
            )
            key = str(key)
            if key not in seen:
                seen.add(key)
                document_keys.append(key)
        return document_keys

    def _source_page_ranges(self, sources: list[Dict[str, Any]]) -> list[str]:
        page_ranges = []
        seen = set()
        for source in sources:
            metadata = source.get("metadata") or {}
            page_start = metadata.get("page_start")
            page_end = metadata.get("page_end")
            if not page_start:
                continue
            if page_end and page_end != page_start:
                page_range = f"{page_start}-{page_end}"
            else:
                page_range = str(page_start)
            if page_range not in seen:
                seen.add(page_range)
                page_ranges.append(page_range)
        return page_ranges

    def _source_sections(self, sources: list[Dict[str, Any]]) -> list[str]:
        sections = []
        seen = set()
        for source in sources:
            metadata = source.get("metadata") or {}
            section = metadata.get("section")
            if not section:
                continue
            section = str(section)
            if section not in seen:
                seen.add(section)
                sections.append(section)
        return sections

    def _source_citation_ids(self, sources: list[Dict[str, Any]]) -> list[Any]:
        citation_ids = []
        seen = set()
        for source in sources:
            metadata = source.get("metadata") or {}
            citation_id = source.get("citation_id") or metadata.get("citation_id")
            if citation_id is None or citation_id in seen:
                continue
            seen.add(citation_id)
            citation_ids.append(citation_id)
        return citation_ids

    def _count_phrase(self, count: int, singular: str, plural: Optional[str] = None) -> str:
        if count == 1:
            return f"1 {singular}"
        return f"{count} {plural or singular + 's'}"

    def _build_recommendation_trace(
        self,
        query: str,
        recommendations: list[Dict[str, Any]],
    ) -> str:
        if not _wants_structured_recommendations(query):
            return "Structured recommendation rows were not requested, so the response will rely on retrieved evidence and tool outputs."
        if not recommendations:
            return "Structured recommendation lookup was requested, but no matching sell-side recommendation rows were available."
        return f"Loaded {len(recommendations)} structured recommendation row(s) for the response payload."

    def _build_synthesis_trace(
        self,
        sources: list[Dict[str, Any]],
        tools_used: list[str],
        tool_source_counts: dict[str, int],
    ) -> str:
        if tools_used:
            tool_summary = ", ".join(
                f"{TOOL_DISPLAY_NAMES.get(tool, tool)} ({tool_source_counts.get(tool, 0)} source(s))"
                for tool in dict.fromkeys(tools_used)
            )
        else:
            tool_summary = "no external tools"

        citation_ids = [
            source.get("citation_id")
            for source in sources
            if source.get("citation_id") is not None
        ]
        citation_preview = ", ".join(f"[{citation_id}]" for citation_id in citation_ids[:6])
        if len(citation_ids) > 6:
            citation_preview += f", plus {len(citation_ids) - 6} more"
        if not citation_preview:
            citation_preview = "none returned"

        document_count = len(self._source_document_keys(sources))
        grounding_note = (
            "Grounding plan: prioritize retrieved report evidence, keep citations "
            "attached to claims, and separate live web context from indexed PDFs when both appear."
        )

        return (
            f"Synthesizing the final answer from {self._count_phrase(len(sources), 'collected source')} "
            f"across {self._count_phrase(document_count, 'unique document')}. "
            f"Tools used: {tool_summary}. Citation IDs available: {citation_preview}. "
            f"{grounding_note}"
        )

    def _build_tool_start_trace(self, tool_name: str, tool_input: Dict[str, Any]) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)

        if tool_name == "search_knowledge_base":
            query = tool_input.get("query") or "the requested report context"
            return f"Searching {display_name} for: '{query}'."

        if tool_name == "query_internal_views":
            asset = tool_input.get("asset_class") or "all asset classes"
            return f"Querying {display_name} for {asset} views."

        if tool_name == "get_analyst_intelligence":
            analyst = tool_input.get("analyst_name")
            sector = tool_input.get("sector")
            target = analyst or sector or "matching analysts"
            return f"Looking up {display_name} for {target}."

        if tool_name == "web_search":
            query = tool_input.get("query") or "market context"
            return f"Searching {display_name} for: '{query}'."

        return f"Running {display_name}."

    def _build_tool_end_trace(self, tool_name: str, source_count: int) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        if source_count == 1:
            return f"Found 1 source from {display_name}."
        if source_count > 1:
            return f"Found {source_count} sources from {display_name}."
        return f"Finished {display_name}."

    def _build_tool_error_trace(self, tool_name: str, error: str) -> str:
        display_name = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
        return f"{display_name} returned an error: {error}"

# Singleton
_orchestrator: Optional[AgentOrchestrator] = None

def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator
