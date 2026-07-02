import unittest
from unittest.mock import patch

from fastapi import HTTPException

import main


class DebugEndpointGateTests(unittest.IsolatedAsyncioTestCase):
    async def test_debug_gate_allows_when_enabled(self):
        with patch.object(main.settings, "ENABLE_DEBUG_ENDPOINTS", True):
            await main.require_debug_endpoints_enabled()

    async def test_debug_gate_returns_404_when_disabled(self):
        with patch.object(main.settings, "ENABLE_DEBUG_ENDPOINTS", False):
            with self.assertRaises(HTTPException) as raised:
                await main.require_debug_endpoints_enabled()

        self.assertEqual(raised.exception.status_code, 404)


class DebugRouteDependencyTests(unittest.TestCase):
    def test_debug_routes_have_debug_gate_dependency(self):
        guarded_paths = {
            "/debug_search",
            "/stats",
            "/debug_recommendations",
        }

        for path in guarded_paths:
            route = next(
                route
                for route in main.app.routes
                if getattr(route, "path", None) == path
            )

            self.assertTrue(
                any(
                    dependency.call is main.require_debug_endpoints_enabled
                    for dependency in route.dependant.dependencies
                ),
                path,
            )
