"""
Shared provider error formatting for user-facing events.
"""
from typing import Optional

import httpx


def format_provider_error(
    error: Exception,
    *,
    provider_name: str,
    action: Optional[str] = None,
    api_key_name: Optional[str] = None,
) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code

        if status_code == 401:
            if api_key_name:
                message = (
                    f"{provider_name} authorization failed. "
                    f"Check {api_key_name} in .env and restart the backend."
                )
            else:
                message = f"{provider_name} authorization failed."
        elif status_code == 429:
            message = f"{provider_name} rate limit reached. Wait a moment and try again."
        else:
            message = f"{provider_name} request failed with HTTP {status_code}."
    elif isinstance(error, httpx.RequestError):
        message = f"Could not reach {provider_name}. Check your network connection and try again."
    else:
        message = str(error)

    return f"{action}: {message}" if action else message


def format_ingestion_error(
    error: Exception,
    *,
    provider_name: str = "Mistral OCR",
    api_key_name: str = "MISTRAL_API_KEY",
) -> str:
    return format_provider_error(
        error,
        provider_name=provider_name,
        api_key_name=api_key_name,
    )


def format_chat_error(error: Exception) -> str:
    return format_provider_error(
        error,
        provider_name="Mistral chat",
        action="I encountered an error processing your request",
        api_key_name="MISTRAL_API_KEY",
    )
