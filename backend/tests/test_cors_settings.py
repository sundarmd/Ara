import unittest

from main import app
from config.settings import Settings


class CorsSettingsTests(unittest.TestCase):
    def test_cors_list_settings_accept_comma_separated_and_json_values(self):
        settings = Settings(
            CORS_ALLOWED_ORIGINS="https://app.example.com, http://localhost:3000",
            CORS_ALLOWED_METHODS="GET,POST",
            CORS_ALLOWED_HEADERS='["Content-Type", "Authorization"]',
        )

        self.assertEqual(
            settings.CORS_ALLOWED_ORIGINS,
            ["https://app.example.com", "http://localhost:3000"],
        )
        self.assertEqual(settings.CORS_ALLOWED_METHODS, ["GET", "POST"])
        self.assertEqual(settings.CORS_ALLOWED_HEADERS, ["Content-Type", "Authorization"])

    def test_default_cors_headers_include_api_key_header(self):
        settings = Settings()

        self.assertIn("X-API-Key", settings.CORS_ALLOWED_HEADERS)

    def test_cors_middleware_uses_explicit_origins_without_credentials_by_default(self):
        cors_middleware = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )

        self.assertNotEqual(cors_middleware.kwargs["allow_origins"], ["*"])
        self.assertFalse(cors_middleware.kwargs["allow_credentials"])


class PublicBaseUrlSettingsTests(unittest.TestCase):
    def test_browser_base_url_defaults_to_localhost_for_zero_bind_host(self):
        settings = Settings(API_HOST="0.0.0.0", API_PORT=9000)

        self.assertEqual(settings.API_BROWSER_BASE_URL, "http://localhost:9000")

    def test_browser_base_url_uses_public_override_without_trailing_slash(self):
        settings = Settings(API_PUBLIC_BASE_URL="https://ara.example.com/api/")

        self.assertEqual(settings.API_BROWSER_BASE_URL, "https://ara.example.com/api")
