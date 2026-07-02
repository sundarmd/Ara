"""
Chunker module for segment-aware text chunking.
"""
import os
from typing import List
import uuid
import tiktoken

from config.settings import settings
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


def _write_table_artifact(doc_id: str, page: int, table_text: str) -> str:
    doc_tables_dir = os.path.join(settings.TABLES_DIR, doc_id)
    os.makedirs(doc_tables_dir, exist_ok=True)

    artifact_path = os.path.join(
        doc_tables_dir,
        f"page-{page}-{uuid.uuid4().hex}.md",
    )
    with open(artifact_path, "w", encoding="utf-8") as table_file:
        table_file.write(table_text)

    return artifact_path


def _is_markdown_separator_row(row: str) -> bool:
    cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
    if not cells:
        return False
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def _split_table_lines(table_text: str) -> tuple[List[str], List[str]]:
    lines = [line.rstrip() for line in table_text.splitlines() if line.strip()]
    if len(lines) >= 2 and _is_markdown_separator_row(lines[1]):
        return lines[:2], lines[2:]
    if lines:
        return lines[:1], lines[1:]
    return [], []


def _format_table_chunk_text(
    *,
    page: int,
    row_start: int,
    row_end: int,
    artifact_path: str,
    header_lines: List[str],
    row_lines: List[str],
) -> str:
    table_lines = header_lines + row_lines
    table_preview = "\n".join(table_lines).strip()
    return (
        f"Table excerpt from page {page}, rows {row_start}-{row_end}.\n"
        f"Full table artifact: {artifact_path}\n\n"
        f"{table_preview}"
    )


def _build_table_chunks(
    *,
    doc_id: str,
    bank: str,
    asset_class: str,
    report_date: str,
    segment: Segment,
    section: str | None,
) -> List[Chunk]:
    table_text = segment.text.strip()
    artifact_path = _write_table_artifact(doc_id, segment.page, table_text)
    header_lines, row_lines = _split_table_lines(table_text)

    if not row_lines:
        return [
            Chunk(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                bank=bank,
                asset_class=asset_class,
                report_date=report_date,
                page_start=segment.page,
                page_end=segment.page,
                section=section,
                segment_types=["table"],
                text=_format_table_chunk_text(
                    page=segment.page,
                    row_start=1,
                    row_end=max(1, len(header_lines)),
                    artifact_path=artifact_path,
                    header_lines=header_lines,
                    row_lines=[],
                ),
                table_artifact_path=artifact_path,
                table_row_start=1,
                table_row_end=max(1, len(header_lines)),
            )
        ]

    chunks: List[Chunk] = []
    current_rows: List[str] = []
    current_row_start = 1

    def flush_rows(row_end: int) -> None:
        nonlocal current_rows, current_row_start
        if not current_rows:
            return
        chunks.append(
            Chunk(
                id=str(uuid.uuid4()),
                doc_id=doc_id,
                bank=bank,
                asset_class=asset_class,
                report_date=report_date,
                page_start=segment.page,
                page_end=segment.page,
                section=section,
                segment_types=["table"],
                text=_format_table_chunk_text(
                    page=segment.page,
                    row_start=current_row_start,
                    row_end=row_end,
                    artifact_path=artifact_path,
                    header_lines=header_lines,
                    row_lines=current_rows,
                ),
                table_artifact_path=artifact_path,
                table_row_start=current_row_start,
                table_row_end=row_end,
            )
        )
        current_rows = []
        current_row_start = row_end + 1

    for row_index, row in enumerate(row_lines, start=1):
        candidate_rows = current_rows + [row]
        candidate_text = _format_table_chunk_text(
            page=segment.page,
            row_start=current_row_start,
            row_end=row_index,
            artifact_path=artifact_path,
            header_lines=header_lines,
            row_lines=candidate_rows,
        )
        if current_rows and _get_token_length(candidate_text) > MAX_TOKENS_PER_CHUNK:
            flush_rows(row_index - 1)
            current_rows.append(row)
            current_row_start = row_index
        else:
            current_rows = candidate_rows

    flush_rows(len(row_lines))
    return chunks


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

        if seg.segment_type == "heading":
            if current_text_parts:
                flush_chunk()
            current_section = seg_text
        elif seg.section and seg.section != current_section:
            if current_text_parts:
                flush_chunk()
            current_section = seg.section

        if seg.segment_type == "table" and seg_tokens > MAX_TOKENS_PER_CHUNK:
            if current_text_parts:
                flush_chunk()
            chunks.extend(
                _build_table_chunks(
                    doc_id=doc_id,
                    bank=bank,
                    asset_class=asset_class,
                    report_date=report_date,
                    segment=seg,
                    section=current_section,
                )
            )
            continue

        # Start a new chunk before adding a segment that would exceed the chunk target.
        # We only flush if we have existing content.
        if (current_token_count + seg_tokens > MAX_TOKENS_PER_CHUNK) and len(current_text_parts) >= 1:
            flush_chunk()

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
                same_section = prev.section == chunk.section
                has_table_artifact = bool(prev.table_artifact_path or chunk.table_artifact_path)
                
                # Check if merging keeps us within reasonable bounds (e.g. 1.2x limit)
                if same_section and not has_table_artifact and prev_tokens + chunk_tokens <= MAX_TOKENS_PER_CHUNK * 1.2:
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
