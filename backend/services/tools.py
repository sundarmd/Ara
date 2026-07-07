"""
Tool definitions for the Agent Orchestrator.
Exposes specific capabilities as callable functions with schemas.
"""
import asyncio
import json
import logging
import re
from contextvars import ContextVar, Token
from datetime import date
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from config.settings import settings
from services.document_store import get_document_store
from services.errors import format_provider_error
from services.rag import search_documents  # RAG
from services.recommendations import get_recommendation_store

from tavily import TavilyClient

logger = logging.getLogger(__name__)

# --- Tool Implementations ---

KB_CITATION_START = 1
INTERNAL_VIEW_CITATION_START = 100
ANALYST_CITATION_START = 200
WEB_CITATION_START = 300
_SEARCH_FILTER_SCOPE: ContextVar[Dict[str, Optional[str]]] = ContextVar(
    "search_filter_scope",
    default={"bank": None, "asset_class": None},
)


def citation_id(range_start: int, index: int) -> int:
    """Return a stable citation ID within a tool-specific range."""
    return range_start + index


def tool_success(sources: List[Dict[str, Any]], message: Optional[str] = None) -> str:
    """Serialize a successful tool result using the shared contract."""
    payload: Dict[str, Any] = {"ok": True, "sources": sources}
    if message:
        payload["message"] = message
    return json.dumps(payload)


def tool_error(message: str) -> str:
    """Serialize a failed tool result using the shared contract."""
    return json.dumps({"ok": False, "error": message, "sources": []})


def set_search_filter_scope(bank: Optional[str], asset_class: Optional[str]) -> Token:
    """Set request-level filters that must apply to knowledge-base searches."""
    return _SEARCH_FILTER_SCOPE.set({"bank": bank, "asset_class": asset_class})


def reset_search_filter_scope(token: Token) -> None:
    """Reset request-level knowledge-base search filters."""
    _SEARCH_FILTER_SCOPE.reset(token)


def effective_search_filter(tool_value: Optional[str], scope_key: str) -> Optional[str]:
    scoped_value = _SEARCH_FILTER_SCOPE.get().get(scope_key)
    return scoped_value if scoped_value is not None else tool_value


def _today_iso() -> str:
    return date.today().isoformat()


def _web_search_time_range(query: str) -> Optional[str]:
    normalized = query.lower()
    if re.search(r"\b(today|daily|intraday|this morning|this afternoon)\b", normalized):
        return "day"
    if re.search(r"\b(latest|current|recent|this week|now|news|headlines)\b", normalized):
        return "week"
    return None


def _date_scoped_web_query(query: str, today_iso: str) -> str:
    if today_iso in query:
        return query
    return f"{query} as of {today_iso}"


class SearchKnowledgeBaseInput(BaseModel):
    query: str = Field(..., description="Natural-language search query for uploaded reports.")
    bank: Optional[str] = Field(None, description="Optional bank/source filter, e.g. GS, JPM, UBS.")
    asset_class: Optional[str] = Field(None, description="Optional asset-class filter, e.g. equity or multi_asset.")

@tool(args_schema=SearchKnowledgeBaseInput)
async def search_knowledge_base(
    query: str,
    bank: Optional[str] = None,
    asset_class: Optional[str] = None,
) -> str:
    """
    Search within the uploaded PDF research reports WITHOUT internal views.
    Use this for questions about external analysis (e.g., 'What does Goldman say about AI?').
    """
    try:
        filter_bank = effective_search_filter(bank, "bank")
        filter_asset_class = effective_search_filter(asset_class, "asset_class")

        results = await search_documents(
            query=query,
            n_results=settings.RAG_SEARCH_RESULTS,
            filter_bank=filter_bank,
            filter_asset_class=filter_asset_class,
        )
        if not results:
            return tool_success([], "No relevant information found in knowledge base.")
        
        tool_output = []
        document_titles: Dict[str, str] = {}
        for i, r in enumerate(results):
            meta = r.get('metadata', {})
            doc_id = meta.get('doc_id')
            page_start = meta.get('page_start', 1)
            page_end = meta.get('page_end', page_start)
            deep_link = f"{settings.API_BROWSER_BASE_URL}/documents/{doc_id}/file#page={page_start}" if doc_id else None
            title = meta.get('title') or meta.get('filename') or 'Unknown Document'

            if doc_id:
                if doc_id not in document_titles:
                    doc = get_document_store().get_document(doc_id)
                    document_titles[doc_id] = (
                        getattr(doc, "title", None)
                        or getattr(doc, "filename", None)
                        or title
                    )
                title = document_titles[doc_id]

            source_entry = {
                "citation_id": citation_id(KB_CITATION_START, i),
                "text": r.get('text', '').strip(),
                "metadata": {
                    "bank": meta.get('bank', 'Unknown'),
                    "report_date": meta.get('report_date', 'N/A'),
                    "title": title,
                    "page_start": page_start,
                    "page_end": page_end,
                    "url": deep_link
                }
            }
            tool_output.append(source_entry)
            
        return tool_success(tool_output)
    except Exception as e:
        logger.error(f"RAG tool error: {e}")
        return tool_error(format_provider_error(
            e,
            provider_name="knowledge base search",
            action="Error searching knowledge base",
        ))

class QueryInternalViewsInput(BaseModel):
    asset_class: Optional[str] = Field(None, description="Filter by asset class (e.g., 'equity', 'fixed_income')")
    include_history: bool = Field(False, description="Set to True to see past recommendations and outcomes.")

@tool(args_schema=QueryInternalViewsInput)
async def query_internal_views(
    asset_class: Optional[str] = None,
    include_history: bool = False
) -> str:
    """
    Get Ara's HOUSE VIEWS and investment stances.
    Use this for questions like "What is our view on Tech?" or "Are we overweight bonds?".
    Set include_history=True to see past performance.
    """
    try:
        store = get_recommendation_store()
        # Fetch active by default, or all if history requested
        is_active = None if include_history else True
        
        recos = await store.get_by_filters(
            bank="Ara", # Force internal
            asset_class=asset_class,
            source_type="internal_view",
            is_active=is_active
        )
        
        if not recos:
            return tool_success([], "No internal views found matching criteria.")
            
        tool_output = []
        for i, r in enumerate(recos):
            # Format text clearly distinguishing current vs historical
            status_str = "CURRENT VIEW" if r.is_active else f"HISTORICAL (Outcome: {r.outcome})"
            text = f"{status_str}: Ara is {r.stance} on {r.asset_class} ({r.sub_asset}). Rationale: {r.rationale} [{r.horizon}]"

            source_entry = {
                "citation_id": citation_id(INTERNAL_VIEW_CITATION_START, i),
                "text": text,
                "metadata": {
                    "bank": "Ara Internal",
                    "title": "Investment Committee Database",
                    "report_date": r.date or "Current"
                }
            }
            tool_output.append(source_entry)
            
        return tool_success(tool_output)

    except Exception as e:
        logger.error(f"Internal view tool error: {e}")
        return tool_error(format_provider_error(
            e,
            provider_name="internal views",
            action="Error querying internal views",
        ))

class AnalystIntelligenceInput(BaseModel):
    analyst_name: Optional[str] = Field(None, description="Name of the analyst (e.g., 'Sarah Chen')")
    sector: Optional[str] = Field(None, description="Sector to find experts for (e.g., 'Technology', 'Luxury')")

@tool(args_schema=AnalystIntelligenceInput)
async def get_analyst_intelligence(
    analyst_name: Optional[str] = None,
    sector: Optional[str] = None
) -> str:
    """
    Look up detailed profiles, bios, and track records of Ara analysts.
    Use this for questions like "Who covers AI?" or "What is Sarah's background?".
    """
    try:
        store = get_recommendation_store()
        analysts = await store.get_analysts(name=analyst_name, sector=sector)
        
        if not analysts:
            return tool_success([], "No analysts found matching criteria.")
            
        tool_output = []
        for i, a in enumerate(analysts):
            text = f"ANALYST PROFILE: {a.name} ({a.team}).\nBio: {a.bio}\nCoverage: {a.coverage_sector}\nAccuracy Score: {a.accuracy_score}"
            
            source_entry = {
                "citation_id": citation_id(ANALYST_CITATION_START, i),
                "text": text,
                "metadata": {
                    "bank": "Ara HR",
                    "title": "Analyst Directory",
                    "report_date": "Current"
                }
            }
            tool_output.append(source_entry)
            
        return tool_success(tool_output)

    except Exception as e:
        logger.error(f"Analyst tool error: {e}")
        return tool_error(format_provider_error(
            e,
            provider_name="analyst intelligence",
            action="Error querying analyst intelligence",
        ))

@tool
async def web_search(query: str) -> str:
    """
    Search the public internet for live data, news, or missing context.
    Use this when internal data is insufficient.
    """
    if not settings.TAVILY_API_KEY:
        return tool_error("Web search is disabled (TAVILY_API_KEY missing).")
        
    try:
        today_iso = _today_iso()
        time_range = _web_search_time_range(query)
        tavily_query = _date_scoped_web_query(query, today_iso) if time_range else query
        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: tavily.search(
                query=tavily_query,
                search_depth="basic",
                topic="finance",
                time_range=time_range,
                max_results=3,
            ),
        )
        
        results = response.get("results", [])
        if not results:
            return tool_success([], "No web search results found.")
            
        tool_output = []
        import urllib.parse

        for i, res in enumerate(results):
            content = res.get('content', '')
            snippet = content[:30].strip()
            safe_snippet = urllib.parse.quote(snippet)

            original_url = res.get("url", "")
            deep_link = f"{original_url}#:~:text={safe_snippet}" if original_url else None
            published_date = res.get("published_date") or res.get("publishedDate")

            source_entry = {
                "citation_id": citation_id(WEB_CITATION_START, i),
                "text": (
                    f"WEB RESULT: {res.get('title')}\n"
                    f"Search date: {today_iso}\n"
                    f"Published: {published_date or 'Unknown'}\n"
                    f"{content}"
                ),
                "metadata": {
                    "bank": "Web",
                    "title": res.get("title", "Web Result"),
                    "report_date": published_date or f"Live as of {today_iso}",
                    "url": deep_link
                }
            }
            tool_output.append(source_entry)
            
        return tool_success(tool_output)

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return tool_error(format_provider_error(
            e,
            provider_name="Tavily web search",
            action="Error performing web search",
            api_key_name="TAVILY_API_KEY",
        ))

# List of tools to be bound to the LangChain agent
# Renamed query_recommendations -> query_internal_views
# Added get_analyst_intelligence
AVAILABLE_TOOLS = [search_knowledge_base, query_internal_views, get_analyst_intelligence, web_search]
