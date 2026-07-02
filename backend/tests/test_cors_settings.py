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

    def test_cors_middleware_uses_explicit_origins_without_credentials_by_default(self):
        cors_middleware = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )

        self.assertNotEqual(cors_middleware.kwargs["allow_origins"], ["*"])
        self.assertFalse(cors_middleware.kwargs["allow_credentials"])
