"""
Chunker module for segment-aware text chunking.
"""
from typing import List
import uuid
import tiktoken

from models.schemas import Segment, Chunk


MAX_TOKENS_PER_CHUNK = 800  # Approx 3000-4000 characters
MIN_TOKENS_PER_CHUNK = 100

# Initialize encoder once
try:
    _ENCODER = tiktoken.get_encoding("cl100k_base")
except Exception:
    # Fallback or strict error
    _ENCODER = tiktoken.get_encoding("gpt2")

def _get_token_length(text: str) -> int:
    """Get token count using pre-initialized encoder."""
    return len(_ENCODER.encode(text))


def build_chunks(
    doc_id: str,
    bank: str,
    asset_class: str,
    report_date: str,
    segments: List[Segment],
) -> List[Chunk]:
    """
    Build chunks from segments with intelligent grouping using token counts.
    
    Args:
        doc_id: Document identifier
        bank: Bank/source of the report (e.g., "GS", "UBS")
        asset_class: Asset class (e.g., "equity", "fixed_income")
        report_date: ISO date string
        segments: List of segments from the document
        
    Returns:
        List of Chunk objects ready for embedding
    """
    chunks: List[Chunk] = []

    current_text_parts: List[str] = []
    current_pages: List[int] = []
    current_segment_types: List[str] = []
    current_section: str | None = None
    
    # Track current chunk size in tokens
    current_token_count = 0

    def flush_chunk():
        nonlocal current_text_parts, current_pages, current_segment_types, current_section, current_token_count
        if not current_text_parts:
            return
        text = "\n\n".join(current_text_parts).strip()
        if not text:
            return

        chunk = Chunk(
            id=str(uuid.uuid4()),
            doc_id=doc_id,
            bank=bank,
            asset_class=asset_class,
            report_date=report_date,
            page_start=min(current_pages),
            page_end=max(current_pages),
            section=current_section,
            segment_types=list(set(current_segment_types)),
            text=text,
        )
        chunks.append(chunk)

        current_text_parts = []
        current_pages = []
        current_segment_types = []
        current_token_count = 0

    for seg in segments:
        seg_text = seg.text.strip()
        if not seg_text:
            continue

        seg_tokens = _get_token_length(seg_text)
        
        # Start new chunk if adding this segment would exceed MAX_TOKENS_PER_CHUNK
        # But if the segment itself is huge (larger than max), we still have to add it (or split it further, 
        # but for now we'll just accept oversized chunks for simplicity rather than split mid-sentence).
        # We only flush if we have existing content.
        if (current_token_count + seg_tokens > MAX_TOKENS_PER_CHUNK) and len(current_text_parts) >= 1:
            flush_chunk()

        # Track section if/when we start detecting it; for now None
        current_section = current_section or seg.section

        current_text_parts.append(seg_text)
        current_pages.append(seg.page)
        current_segment_types.append(seg.segment_type)
        current_token_count += seg_tokens

    # Flush final chunk
    flush_chunk()

    # Merge any tiny chunks with previous if possible
    merged: List[Chunk] = []
    for chunk in chunks:
        if merged:
            chunk_tokens = _get_token_length(chunk.text)
            if chunk_tokens < MIN_TOKENS_PER_CHUNK:
                prev = merged[-1]
                prev_tokens = _get_token_length(prev.text)
                
                # Check if merging keeps us within reasonable bounds (e.g. 1.2x limit)
                if prev_tokens + chunk_tokens <= MAX_TOKENS_PER_CHUNK * 1.2:
                    combined_text = prev.text + "\n\n" + chunk.text
                    
                    # Create new chunk with merged data
                    merged[-1] = Chunk(
                        id=prev.id,
                        doc_id=prev.doc_id,
                        bank=prev.bank,
                        asset_class=prev.asset_class,
                        report_date=prev.report_date,
                        page_start=prev.page_start,
                        page_end=max(prev.page_end, chunk.page_end),
                        section=prev.section,
                        segment_types=list(set(prev.segment_types + chunk.segment_types)),
                        text=combined_text,
                    )
                else:
                    merged.append(chunk)
            else:
                merged.append(chunk)
        else:
            merged.append(chunk)

    return merged
