"""
Tool definitions for the Agent Orchestrator.
Exposes specific capabilities as callable functions with schemas.
"""
import logging
from contextvars import ContextVar, Token
from typing import List, Optional, Dict, Any, Annotated
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from config.settings import settings
from services.document_store import get_document_store
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


def set_search_filter_scope(bank: Optional[str], asset_class: Optional[str]) -> Token:
    """Set request-level filters that must apply to knowledge-base searches."""
    return _SEARCH_FILTER_SCOPE.set({"bank": bank, "asset_class": asset_class})


def reset_search_filter_scope(token: Token) -> None:
    """Reset request-level knowledge-base search filters."""
    _SEARCH_FILTER_SCOPE.reset(token)


def effective_search_filter(tool_value: Optional[str], scope_key: str) -> Optional[str]:
    scoped_value = _SEARCH_FILTER_SCOPE.get().get(scope_key)
    return scoped_value if scoped_value is not None else tool_value


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
            n_results=4,
            filter_bank=filter_bank,
            filter_asset_class=filter_asset_class,
        )
        if not results:
            return "No relevant information found in knowledge base."
        
        tool_output = []
        document_titles: Dict[str, str] = {}
        for i, r in enumerate(results):
            meta = r.get('metadata', {})
            doc_id = meta.get('doc_id')
            page_start = meta.get('page_start', 1)
            page_end = meta.get('page_end', page_start)
            deep_link = f"{settings.API_BASE_URL}/documents/{doc_id}/file#page={page_start}" if doc_id else None
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
            
        import json
        return json.dumps(tool_output)
    except Exception as e:
        logger.error(f"RAG tool error: {e}")
        return f"Error searching knowledge base: {str(e)}"

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
            return "No internal views found matching criteria."
            
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
            
        import json
        return json.dumps(tool_output)

    except Exception as e:
        logger.error(f"Internal view tool error: {e}")
        return f"Error querying internal views: {str(e)}"

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
            return "No analysts found matching criteria."
            
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
            
        import json
        return json.dumps(tool_output)

    except Exception as e:
        logger.error(f"Analyst tool error: {e}")
        return f"Error querying analyst intelligence: {str(e)}"

@tool
async def web_search(query: str) -> str:
    """
    Search the public internet for live data, news, or missing context.
    Use this when internal data is insufficient.
    """
    if not settings.TAVILY_API_KEY:
        return "Web search is disabled (TAVILY_API_KEY missing)."
        
    try:
        tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        # Deep search for better quality
        response = tavily.search(query=query, search_depth="basic", max_results=3)
        
        results = response.get("results", [])
        if not results:
            return "No web search results found."
            
        tool_output = []
        import urllib.parse

        for i, res in enumerate(results):
            content = res.get('content', '')
            snippet = content[:30].strip()
            safe_snippet = urllib.parse.quote(snippet)

            original_url = res.get("url", "")
            deep_link = f"{original_url}#:~:text={safe_snippet}" if original_url else None

            source_entry = {
                "citation_id": citation_id(WEB_CITATION_START, i),
                "text": f"WEB RESULT: {res.get('title')}\n{content}",
                "metadata": {
                    "bank": "Web",
                    "title": res.get("title", "Web Result"),
                    "report_date": "Live",
                    "url": deep_link
                }
            }
            tool_output.append(source_entry)
            
        import json
        return json.dumps(tool_output)

    except Exception as e:
        logger.error(f"Web search error: {e}")
        return f"Error performing web search: {str(e)}"

# List of tools to be bound to the LangChain agent
# Renamed query_recommendations -> query_internal_views
# Added get_analyst_intelligence
AVAILABLE_TOOLS = [search_knowledge_base, query_internal_views, get_analyst_intelligence, web_search]
