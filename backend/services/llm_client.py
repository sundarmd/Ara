"""
Unified LLM Client Service.

Centralizes interactions with the Mistral API, handling:
- Authentication
- Retries (Exponential Backoff)
- Error Handling
- JSON Response Parsing
"""
import json
import logging
import asyncio
from typing import Dict, Any, List, Optional, Union
import httpx

from config.settings import settings

logger = logging.getLogger(__name__)

class LLMClient:
    """
    Robust client for Mistral API interactions.
    """
    
    def __init__(self):
        self.api_key = settings.MISTRAL_API_KEY
        self.base_url = "https://api.mistral.ai/v1"
        self.timeout = settings.TIMEOUT_CHAT
        
    async def _make_request(
        self, 
        endpoint: str, 
        payload: Dict[str, Any], 
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Execute API request with retries.
        """
        if not self.api_key:
            raise ValueError("MISTRAL_API_KEY is not set")

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(url, headers=headers, json=payload)
                    
                    if response.status_code == 429: # Rate limit
                        wait_time = 2 ** attempt
                        logger.warning(f"Rate limited. Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        continue
                        
                    response.raise_for_status()
                    return response.json()
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} - {e.response.text}")
                if attempt == retries - 1:
                    raise
            except httpx.RequestError as e:
                logger.error(f"Request failed: {e}")
                if attempt == retries - 1:
                    raise
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                if attempt == retries - 1:
                    raise
                    
            # Backoff for other errors
            await asyncio.sleep(1 * (attempt + 1))
            
        raise Exception("Max retries reached")

    async def get_chat_completion(
        self, 
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        json_mode: bool = False
    ) -> Union[str, Dict[str, Any]]:
        """
        Get chat completion from Mistral.
        
        Args:
            messages: List of message dicts {"role": "...", "content": "..."}
            model: Model name override
            temperature: Sampling temperature
            max_tokens: Max output tokens
            json_mode: If True, requests JSON response and parses it
            
        Returns:
            String content or Parsed JSON dict
        """
        payload = {
            "model": model or settings.MISTRAL_CHAT_MODEL,
            "messages": messages,
            "temperature": temperature,
        }
        
        if max_tokens:
            payload["max_tokens"] = max_tokens
            
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        response_data = await self._make_request("/chat/completions", payload)
        content = response_data["choices"][0]["message"]["content"]
        
        if json_mode:
            return self._clean_and_parse_json(content)
            
        return content

    def _clean_and_parse_json(self, content: str) -> Dict[str, Any]:
        """
        Clean markdown code blocks and parse JSON.
        """
        cleaned = content.strip()
        
        # Remove markdown code blocks
        if cleaned.startswith("```"):
            # Find first newline
            first_newline = cleaned.find("\n")
            if first_newline != -1:
                 # Check if language identifier exists
                if cleaned[:first_newline].strip().lower().startswith("```json"):
                     cleaned = cleaned[first_newline+1:]
                else:
                     cleaned = cleaned[3:]
                     
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
                
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON content: {content[:100]}...")
            raise e


# Singleton instance
_llm_client: Optional[LLMClient] = None

def get_llm_client() -> LLMClient:
    """Get or create the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
