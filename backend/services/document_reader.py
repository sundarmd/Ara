"""
Document reader module for parsing PDF files using Mistral OCR API.
"""
import base64
import os
import re
from typing import List, Optional
import httpx

from config.settings import settings
from models.schemas import Segment


async def parse_pdf_to_segments(doc_id: str, file_path: str) -> List[Segment]:
    """
    Parse PDF using Mistral OCR API and return structured segments.
    
    Args:
        doc_id: Unique identifier for the document
        file_path: Path to the PDF file
        
    Returns:
        List of Segment objects extracted from the PDF
    """
    # Read PDF file and encode as base64
    with open(file_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    # Call Mistral OCR API
    async with httpx.AsyncClient(timeout=settings.TIMEOUT_OCR) as client:
        response = await client.post(
            settings.MISTRAL_OCR_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mistral-ocr-latest",
                "document": {
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{pdf_data}"
                },
                "include_image_base64": True,
            },
        )
        response.raise_for_status()
        ocr_result = response.json()
    
    # Parse OCR response into segments
    segments = _parse_ocr_response(doc_id, ocr_result)
    
    return segments


def _parse_ocr_response(doc_id: str, ocr_result: dict) -> List[Segment]:
    """
    Parse Mistral OCR response into Segment objects.
    
    Segment type mapping:
    - # ## ### headings → "heading"
    - Markdown tables (|...|) → "table"
    - ![caption](...) → "caption"
    - Regular paragraphs → "body"
    """
    segments: List[Segment] = []
    current_section: Optional[str] = None
    
    pages = ocr_result.get("pages", [])
    
    for page_data in pages:
        page_num = page_data.get("index", 0) + 1
        markdown = page_data.get("markdown", "")
        images = page_data.get("images", [])
        
        # Save images from this page
        image_paths = _save_page_images(doc_id, page_num, images)
        
        # Parse markdown into segments
        page_segments = _parse_markdown_to_segments(
            doc_id=doc_id,
            page=page_num,
            markdown=markdown,
            current_section=current_section,
            image_paths=image_paths,
        )
        
        # Update current section from headings
        for seg in page_segments:
            if seg.segment_type == "heading":
                current_section = seg.text
        
        segments.extend(page_segments)
    
    return segments


def _save_page_images(doc_id: str, page: int, images: List[dict]) -> dict:
    """
    Save base64 images to disk and return mapping of image IDs to paths.
    """
    doc_images_dir = os.path.join(settings.IMAGES_DIR, doc_id)
    os.makedirs(doc_images_dir, exist_ok=True)
    image_paths = {}
    
    for idx, img_data in enumerate(images):
        image_id = img_data.get("id", f"img_{idx}")
        base64_data = img_data.get("image_base64", "")
        
        if not base64_data:
            continue
        
        # Determine file extension from base64 header or default to png
        ext = "png"
        if base64_data.startswith("data:image/"):
            match = re.match(r"data:image/(\w+);base64,", base64_data)
            if match:
                ext = match.group(1)
                base64_data = base64_data.split(",", 1)[1]
        
        # Save image
        filename = f"{page}_{idx}.{ext}"
        filepath = os.path.join(doc_images_dir, filename)
        
        try:
            img_bytes = base64.b64decode(base64_data)
            with open(filepath, "wb") as f:
                f.write(img_bytes)
            image_paths[image_id] = filepath
        except Exception:
            # Skip invalid images
            continue
    
    return image_paths


def _parse_markdown_to_segments(
    doc_id: str,
    page: int,
    markdown: str,
    current_section: Optional[str],
    image_paths: dict,
) -> List[Segment]:
    """
    Parse markdown content into typed segments.
    """
    segments: List[Segment] = []
    
    # Split by double newline to get blocks
    blocks = [b.strip() for b in markdown.split("\n\n") if b.strip()]
    
    for block in blocks:
        segment = _classify_block(
            doc_id=doc_id,
            page=page,
            block=block,
            section=current_section,
            image_paths=image_paths,
        )
        if segment:
            segments.append(segment)
            # Update section if this is a heading
            if segment.segment_type == "heading":
                current_section = segment.text
    
    return segments


def _classify_block(
    doc_id: str,
    page: int,
    block: str,
    section: Optional[str],
    image_paths: dict,
) -> Optional[Segment]:
    """
    Classify a markdown block and return appropriate Segment.
    """
    block = block.strip()
    if not block:
        return None
    
    # Check for heading (# ## ### etc)
    heading_match = re.match(r'^(#{1,6})\s+(.+)$', block, re.MULTILINE)
    if heading_match:
        heading_text = heading_match.group(2).strip()
        return Segment(
            doc_id=doc_id,
            page=page,
            segment_type="heading",
            section=section,
            text=heading_text,
            image_path=None,
        )
    
    # Check for table (lines with |)
    if _is_markdown_table(block):
        return Segment(
            doc_id=doc_id,
            page=page,
            segment_type="table",
            section=section,
            text=block,
            image_path=None,
        )
    
    # Check for image reference ![caption](url)
    image_match = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', block)
    if image_match:
        caption = image_match.group(1) or "Image"
        image_ref = image_match.group(2)
        # Look up actual image path if available
        img_path = image_paths.get(image_ref)
        return Segment(
            doc_id=doc_id,
            page=page,
            segment_type="caption",
            section=section,
            text=caption,
            image_path=img_path,
        )
    
    # Default: body text
    return Segment(
        doc_id=doc_id,
        page=page,
        segment_type="body",
        section=section,
        text=block,
        image_path=None,
    )


def _is_markdown_table(block: str) -> bool:
    """Check if block is a markdown table."""
    lines = [line.strip() for line in block.strip().split("\n") if line.strip()]
    if len(lines) < 2:
        return False

    if _looks_like_pipe_table(lines):
        return True
    if _looks_like_whitespace_table(lines):
        return True
    return _looks_like_key_value_table(lines)


def _pipe_cells(line: str) -> List[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|") if cell.strip()]


def _looks_like_pipe_table(lines: List[str]) -> bool:
    pipe_lines = [line for line in lines if "|" in line]
    if len(pipe_lines) < 2 or len(pipe_lines) != len(lines):
        return False

    for line in pipe_lines:
        if re.match(r'^\|?[\s\-:]+\|[\s\-:|]+\|?$', line):
            return True

    return all(len(_pipe_cells(line)) >= 2 for line in pipe_lines)


def _looks_like_whitespace_table(lines: List[str]) -> bool:
    if len(lines) < 3:
        return False

    rows = [re.split(r"\s{2,}|\t+", line.strip()) for line in lines]
    column_counts = [len([cell for cell in row if cell.strip()]) for row in rows]
    if min(column_counts) < 2:
        return False

    return max(column_counts) - min(column_counts) <= 1


def _looks_like_key_value_table(lines: List[str]) -> bool:
    if len(lines) < 3:
        return False

    key_value_pattern = re.compile(r"^[A-Za-z][A-Za-z0-9 /%()._-]{0,40}\s*[:=]\s*\S+")
    return all(key_value_pattern.match(line) for line in lines)
