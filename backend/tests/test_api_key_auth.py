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


class DeleteRouteAuthTests(unittest.TestCase):
    def test_delete_route_has_api_key_dependency(self):
        delete_route = next(
            route
            for route in main.app.routes
            if getattr(route, "path", None) == "/documents/{doc_id}"
            and "DELETE" in getattr(route, "methods", set())
        )

        self.assertTrue(
            any(
                dependency.call is main.verify_api_key
                for dependency in delete_route.dependant.dependencies
            )
        )
