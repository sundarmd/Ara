import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from services import tools


class ToolCitationTests(unittest.IsolatedAsyncioTestCase):
    async def test_knowledge_base_citations_use_knowledge_base_range(self):
        search_results = [
            {"text": "First KB chunk", "metadata": {"doc_id": "doc-1"}},
            {"text": "Second KB chunk", "metadata": {"doc_id": "doc-2"}},
        ]

        with patch.object(tools, "search_documents", AsyncMock(return_value=search_results)):
            output = await tools.search_knowledge_base.ainvoke({"query": "EM assets"})

        sources = json.loads(output)
        self.assertEqual([source["citation_id"] for source in sources], [1, 2])

    async def test_internal_view_citations_use_internal_range(self):
        store = Mock()
        store.get_by_filters = AsyncMock(
            return_value=[
                SimpleNamespace(
                    is_active=True,
                    outcome=None,
                    stance="overweight",
                    asset_class="equity",
                    sub_asset="US tech",
                    rationale="AI capex support",
                    horizon="12m",
                    date="Current",
                ),
                SimpleNamespace(
                    is_active=False,
                    outcome="closed positive",
                    stance="neutral",
                    asset_class="fixed_income",
                    sub_asset="duration",
                    rationale="Curve risk",
                    horizon="6m",
                    date="2025-01-01",
                ),
            ]
        )

        with patch.object(tools, "get_recommendation_store", return_value=store):
            output = await tools.query_internal_views.ainvoke(
                {"asset_class": None, "include_history": True}
            )

        sources = json.loads(output)
        self.assertEqual([source["citation_id"] for source in sources], [100, 101])

    async def test_analyst_citations_use_analyst_range(self):
        store = Mock()
        store.get_analysts = AsyncMock(
            return_value=[
                SimpleNamespace(
                    name="Sarah Chen",
                    team="Equity Strategy",
                    bio="AI infrastructure specialist",
                    coverage_sector="Technology",
                    accuracy_score=0.91,
                )
            ]
        )

        with patch.object(tools, "get_recommendation_store", return_value=store):
            output = await tools.get_analyst_intelligence.ainvoke(
                {"analyst_name": None, "sector": "Technology"}
            )

        sources = json.loads(output)
        self.assertEqual([source["citation_id"] for source in sources], [200])

    async def test_web_citations_use_web_range(self):
        tavily_client = Mock()
        tavily_client.search.return_value = {
            "results": [
                {
                    "title": "Market update",
                    "content": "Markets moved higher after central bank guidance.",
                    "url": "https://example.com/markets",
                },
                {
                    "title": "Policy update",
                    "content": "Policy expectations shifted across rates markets.",
                    "url": "https://example.com/policy",
                },
            ]
        }

        with (
            patch.object(tools.settings, "TAVILY_API_KEY", "tvly-test"),
            patch.object(tools, "TavilyClient", return_value=tavily_client),
        ):
            output = await tools.web_search.ainvoke({"query": "markets"})

        sources = json.loads(output)
        self.assertEqual([source["citation_id"] for source in sources], [300, 301])

