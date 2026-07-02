from typing import Literal, Optional, List
from pydantic import BaseModel, Field


class ReportMetadata(BaseModel):
    """Metadata for a research report."""
    id: str                # internal UUID
    bank: str              # e.g. "GS", "UBS", "JPM"
    asset_class: str       # e.g. "equity", "fixed_income", "multi_asset"
    report_date: str       # ISO date string "YYYY-MM-DD"
    title: Optional[str] = None
    file_path: str         # absolute or relative path to stored PDF


class Segment(BaseModel):
    """A segment of text extracted from a PDF page."""
    doc_id: str
    page: int
    segment_type: Literal["heading", "body", "caption", "table", "other"]
    section: Optional[str] = None
    text: str
    image_path: Optional[str] = None  # Path to extracted image if applicable


class Chunk(BaseModel):
    """A chunk of text ready for embedding and vector storage."""
    id: str
    doc_id: str
    bank: str
    asset_class: str
    report_date: str
    page_start: int
    page_end: int
    section: Optional[str]
    segment_types: List[str]
    text: str


# Chat-related models
class ChatMessage(BaseModel):
    """A single message in a chat conversation."""
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    """Request for chat endpoint."""
    messages: List[ChatMessage] = Field(..., min_length=1)
    bank: Optional[str] = None  # Optional filter
    asset_class: Optional[str] = None  # Optional filter


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    answer: str
    sources: List[dict] = []
    recommendations: List[dict] = []


class DocumentUpload(BaseModel):
    filename: str
    content: str


class QueryRequest(BaseModel):
    query: str


class Recommendation(BaseModel):
    """A structured investment recommendation extracted from a research report."""
    id: str
    doc_id: Optional[str] = None
    bank: str
    source_type: str = "sell_side"  # sell_side, internal, analyst_tracking
    asset_class: str  # equity, fixed_income, multi_asset, fx, rates, credit
    sub_asset: Optional[str] = None  # EM local rates, US HY, etc.
    stance: str  # OW, UW, Neutral, Long, Short
    horizon: Optional[str] = None  # 3m, 6-12m, etc.
    rationale: str
    page: Optional[int] = None
    section: Optional[str] = None
    confidence: Optional[str] = None
    date: Optional[str] = None


# SSE Streaming Event Models
class StreamEventType:
    """Event type constants for SSE streaming."""
    THOUGHT = "thought"
    TOKEN = "token"
    COMPLETE = "complete"
    ERROR = "error"


class ThoughtEvent(BaseModel):
    """Agent reasoning step event for SSE streaming."""
    type: Literal["thought"] = "thought"
    phase: Literal["analyzing", "searching", "extracting", "generating"]
    content: str
    elapsed_ms: int = 0
    details: Optional[List[dict]] = None  # Source previews, recommendations, etc.


class TokenEvent(BaseModel):
    """Single response token event for SSE streaming."""
    type: Literal["token"] = "token"
    content: str


class CompleteEvent(BaseModel):
    """Final response event with sources and recommendations."""
    type: Literal["complete"] = "complete"
    answer: str
    sources: List[dict] = []
    recommendations: List[dict] = []


class ErrorEvent(BaseModel):
    """Error event for SSE streaming."""
    type: Literal["error"] = "error"
    message: str
    code: Optional[str] = None
