"""
Metadata extraction service using LLM to parse document content.
Extracts bank, asset class, and report date from the first page of PDFs.
"""
import json
import logging
from typing import Optional
from dataclasses import dataclass

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentMetadata:
    """Extracted metadata from a research report."""
    bank: str
    asset_class: str
    report_date: str  # ISO format YYYY-MM-DD, or UNKNOWN when unavailable
    title: Optional[str] = None





async def extract_metadata_from_content(text: str) -> Optional[DocumentMetadata]:
    """
    Use Mistral LLM to extract metadata from document content.
    """
    if not text or len(text.strip()) < 50:
        logger.warning("Text too short for metadata extraction")
        return None
    
    # Use first ~3000 chars (usually first page)
    excerpt = text[:3000]
    
    # Load prompt template
    from services.prompt_loader import load_prompt
    from services.llm_client import get_llm_client
    
    prompt = load_prompt("metadata_extraction", excerpt=excerpt)
    
    try:
        client = get_llm_client()
        messages = [{"role": "user", "content": prompt}]
        
        # Call LLM with JSON mode
        parsed = await client.get_chat_completion(
            messages=messages,
            temperature=0.1,
            max_tokens=200,
            json_mode=True
        )
        
        # Validate required fields
        bank = parsed.get("bank") or "UNKNOWN"
        asset_class = parsed.get("asset_class") or "UNKNOWN"
        report_date = parsed.get("report_date") or "UNKNOWN"
        title = parsed.get("title")
        
        if bank == "UNKNOWN" or asset_class == "UNKNOWN" or report_date == "UNKNOWN":
            logger.warning(f"Incomplete metadata extraction: bank={bank}, asset_class={asset_class}, date={report_date}")
            # Still return what we have, use defaults for unknowns
            if bank == "UNKNOWN":
                bank = "UNKNOWN"
            if asset_class == "UNKNOWN":
                asset_class = "unknown"
            if report_date == "UNKNOWN":
                report_date = "UNKNOWN"
        
        return DocumentMetadata(
            bank=bank.upper(),
            asset_class=asset_class.lower().replace("-", "_"),
            report_date=report_date,
            title=title,
        )
            
    except Exception as e:
        logger.error(f"Metadata extraction failed: {e}")
        return None
