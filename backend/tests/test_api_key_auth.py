import unittest
from unittest.mock import patch

from fastapi import HTTPException

import main


class ApiKeyAuthTests(unittest.IsolatedAsyncioTestCase):
    async def test_verify_api_key_is_noop_when_auth_is_disabled(self):
        with patch.object(main.settings, "REQUIRE_API_KEY", False):
            await main.verify_api_key(None)

    async def test_verify_api_key_accepts_configured_key(self):
        with (
            patch.object(main.settings, "REQUIRE_API_KEY", True),
            patch.object(main.settings, "API_KEY", "secret"),
        ):
            await main.verify_api_key("secret")

    async def test_verify_api_key_rejects_invalid_key(self):
        with (
            patch.object(main.settings, "REQUIRE_API_KEY", True),
            patch.object(main.settings, "API_KEY", "secret"),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.verify_api_key("wrong")

        self.assertEqual(raised.exception.status_code, 401)

    async def test_verify_api_key_fails_closed_when_required_key_is_missing(self):
        with (
            patch.object(main.settings, "REQUIRE_API_KEY", True),
            patch.object(main.settings, "API_KEY", None),
        ):
            with self.assertRaises(HTTPException) as raised:
                await main.verify_api_key("secret")

        self.assertEqual(raised.exception.status_code, 500)


class ApiKeyProtectedRouteTests(unittest.TestCase):
    def _route_has_api_key_dependency(self, path: str, method: str) -> bool:
        route = next(
            route
            for route in main.app.routes
            if getattr(route, "path", None) == path
            and method in getattr(route, "methods", set())
        )

        return any(
            dependency.call is main.verify_api_key
            for dependency in route.dependant.dependencies
        )

    def test_mutating_and_data_routes_have_api_key_dependency(self):
        protected_routes = [
            ("/upload", "POST"),
            ("/documents", "GET"),
            ("/documents/{doc_id}", "DELETE"),
            ("/chat/stream", "POST"),
        ]

        for path, method in protected_routes:
            with self.subTest(path=path, method=method):
                self.assertTrue(self._route_has_api_key_dependency(path, method))
