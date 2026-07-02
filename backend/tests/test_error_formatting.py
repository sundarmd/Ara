import unittest

import httpx

from services.errors import (
    format_chat_error,
    format_ingestion_error,
    format_provider_error,
)


def http_status_error(status_code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://api.example.test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError("request failed", request=request, response=response)


class ErrorFormattingTests(unittest.TestCase):
    def test_ingestion_error_preserves_ocr_auth_message(self):
        message = format_ingestion_error(http_status_error(401))

        self.assertEqual(
            message,
            "Mistral OCR authorization failed. Check MISTRAL_API_KEY in .env and restart the backend.",
        )

    def test_provider_error_adds_action_prefix_for_runtime_errors(self):
        message = format_provider_error(
            RuntimeError("vector failed"),
            provider_name="knowledge base search",
            action="Error searching knowledge base",
        )

        self.assertEqual(message, "Error searching knowledge base: vector failed")

    def test_chat_error_uses_shared_provider_format(self):
        message = format_chat_error(http_status_error(429))

        self.assertEqual(
            message,
            "I encountered an error processing your request: Mistral chat rate limit reached. Wait a moment and try again.",
        )
