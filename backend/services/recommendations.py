"""
Recommendation extraction and storage service.

Uses Mistral Chat API to extract structured investment recommendations
from research report markdown.
"""
import json
import os
import uuid
import sqlite3
import shutil
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import httpx
import logging
from pydantic import BaseModel

from config.settings import settings
from models.schemas import Recommendation

logger = logging.getLogger(__name__)

RECOMMENDATION_EXTRACTION_MAX_CHARS = 20000

# --- New Models for Internal Intelligence ---

class Analyst(BaseModel):
    id: str
    name: str
    team: str
    bio: str
    coverage_sector: str
    accuracy_score: float

class InternalView(Recommendation):
    # Extends Recommendation with internal metadata
    analyst_id: Optional[str] = None
    is_active: bool = True
    outcome: Optional[str] = None # For historical records


RECOMMENDATION_DB_COLUMNS: Tuple[str, ...] = (
    "id",
    "doc_id",
    "source_type",
    "bank",
    "asset_class",
    "sub_asset",
    "stance",
    "confidence",
    "horizon",
    "rationale",
    "page",
    "section",
    "date",
    "analyst_id",
    "is_active",
    "outcome",
)

RECOMMENDATION_DB_COLUMN_TYPES: Dict[str, str] = {
    "id": "TEXT",
    "doc_id": "TEXT",
    "source_type": "TEXT",
    "bank": "TEXT",
    "asset_class": "TEXT",
    "sub_asset": "TEXT",
    "stance": "TEXT",
    "confidence": "TEXT",
    "horizon": "TEXT",
    "rationale": "TEXT",
    "page": "INTEGER",
    "section": "TEXT",
    "date": "TEXT",
    "analyst_id": "TEXT",
    "is_active": "INTEGER DEFAULT 1",
    "outcome": "TEXT",
}


def _recommendation_to_db_values(recommendation: Recommendation) -> Tuple[Any, ...]:
    analyst_id = getattr(recommendation, "analyst_id", None)
    is_active = getattr(recommendation, "is_active", True)
    outcome = getattr(recommendation, "outcome", None)

    return (
        recommendation.id,
        recommendation.doc_id,
        recommendation.source_type,
        recommendation.bank,
        recommendation.asset_class,
        recommendation.sub_asset,
        recommendation.stance,
        recommendation.confidence,
        recommendation.horizon,
        recommendation.rationale,
        recommendation.page,
        recommendation.section,
        recommendation.date or datetime.utcnow().isoformat(),
        analyst_id,
        1 if is_active else 0,
        outcome,
    )


def _row_to_internal_view(row: sqlite3.Row) -> InternalView:
    return InternalView(
        id=row["id"],
        doc_id=row["doc_id"],
        bank=row["bank"] or "Unknown",
        source_type=row["source_type"],
        asset_class=row["asset_class"],
        sub_asset=row["sub_asset"],
        stance=row["stance"],
        confidence=row["confidence"],
        horizon=row["horizon"],
        rationale=row["rationale"],
        page=row["page"],
        section=row["section"],
        date=row["date"],
        analyst_id=row["analyst_id"],
        is_active=bool(row["is_active"]),
        outcome=row["outcome"],
    )


class RecommendationStore:
    """
    SQLite-backed storage for recommendations and analyst intelligence.
    
    Persists structured recommendations extracted from research reports
    or generated as mock internal views.
    """
    
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or settings.recommendations_db_path
        if db_path is None:
            self._copy_legacy_db_if_needed()
        self._init_db()

    def _copy_legacy_db_if_needed(self):
        """Copy the pre-split reports/recommendations.db forward on first startup."""
        legacy_db_path = os.path.join(settings.reports_dir, "recommendations.db")
        if self.db_path == legacy_db_path:
            return
        if os.path.exists(self.db_path) or not os.path.exists(legacy_db_path):
            return

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        shutil.copy2(legacy_db_path, self.db_path)
        
    def _init_db(self):
        """Initialize the database schema with migration support."""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            # Check if recommendations table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='recommendations'
            """)
            table_exists = cursor.fetchone() is not None

            if table_exists:
                # Table exists - check if we need to migrate old schema
                cursor = conn.execute("PRAGMA table_info(recommendations)")
                columns = [row[1] for row in cursor.fetchall()]

                # Migration: Rename old columns to new ones
                if 'source_name' in columns and 'bank' not in columns:
                    logger.info("Migrating recommendations table: source_name -> bank")
                    conn.execute("ALTER TABLE recommendations RENAME COLUMN source_name TO bank")
                    columns[columns.index('source_name')] = 'bank'

                if 'sub_asset_class' in columns and 'sub_asset' not in columns:
                    logger.info("Migrating recommendations table: sub_asset_class -> sub_asset")
                    conn.execute("ALTER TABLE recommendations RENAME COLUMN sub_asset_class TO sub_asset")
                    columns[columns.index('sub_asset_class')] = 'sub_asset'

                if 'time_horizon' in columns and 'horizon' not in columns:
                    logger.info("Migrating recommendations table: time_horizon -> horizon")
                    conn.execute("ALTER TABLE recommendations RENAME COLUMN time_horizon TO horizon")
                    columns[columns.index('time_horizon')] = 'horizon'

                for column_name in RECOMMENDATION_DB_COLUMNS:
                    if column_name not in columns:
                        logger.info(f"Adding recommendations.{column_name} column")
                        column_type = RECOMMENDATION_DB_COLUMN_TYPES[column_name]
                        conn.execute(f"ALTER TABLE recommendations ADD COLUMN {column_name} {column_type}")
                        columns.append(column_name)

                conn.commit()
                logger.info("Database schema migration complete")
            else:
                # Fresh install - create new schema
                logger.info("Creating fresh recommendations database schema")

                # 1. Recommendations Table
                conn.execute("""
                    CREATE TABLE recommendations (
                        id TEXT PRIMARY KEY,
                        doc_id TEXT,
                        source_type TEXT,
                        bank TEXT,
                        asset_class TEXT,
                        sub_asset TEXT,
                        stance TEXT,
                        confidence TEXT,
                        horizon TEXT,
                        rationale TEXT,
                        page INTEGER,
                        section TEXT,
                        date TEXT,
                        analyst_id TEXT,
                        is_active INTEGER DEFAULT 1,
                        outcome TEXT
                    )
                """)

                # 2. Analysts Table
                conn.execute("""
                    CREATE TABLE analysts (
                        id TEXT PRIMARY KEY,
                        name TEXT,
                        team TEXT,
                        bio TEXT,
                        coverage_sector TEXT,
                        accuracy_score REAL
                    )
                """)

                conn.commit()
                logger.info("Database schema created successfully")
    
    # --- Analyst Methods ---
    
    async def save_analysts(self, analysts: List[Analyst]) -> None:
        """Save analyst profiles to SQLite."""
        if not analysts:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            for a in analysts:
                conn.execute("""
                    INSERT OR REPLACE INTO analysts 
                    (id, name, team, bio, coverage_sector, accuracy_score)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (a.id, a.name, a.team, a.bio, a.coverage_sector, a.accuracy_score))
            conn.commit()
    
    async def get_analysts(self, name: Optional[str] = None, sector: Optional[str] = None) -> List[Analyst]:
        """Get analysts matching filters."""
        query = "SELECT * FROM analysts WHERE 1=1"
        params: List[Any] = []
        
        if name:
            query += " AND name LIKE ?"
            params.append(f"%{name}%")
        if sector:
            query += " AND coverage_sector LIKE ?"
            params.append(f"%{sector}%")
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            return [
                Analyst(
                    id=row["id"],
                    name=row["name"],
                    team=row["team"],
                    bio=row["bio"],
                    coverage_sector=row["coverage_sector"],
                    accuracy_score=row["accuracy_score"]
                ) for row in rows
            ]

    # --- Recommendation Methods ---

    async def save_recommendations(self, recommendations: List[Recommendation]) -> None:
        """Save recommendations to SQLite."""
        if not recommendations:
            return
            
        with sqlite3.connect(self.db_path) as conn:
            columns_sql = ", ".join(RECOMMENDATION_DB_COLUMNS)
            placeholders_sql = ", ".join(["?"] * len(RECOMMENDATION_DB_COLUMNS))
            for r in recommendations:
                try:
                    conn.execute(f"""
                        INSERT INTO recommendations
                        ({columns_sql})
                        VALUES ({placeholders_sql})
                    """, _recommendation_to_db_values(r))
                except sqlite3.IntegrityError:
                    logger.warning("Duplicate recommendation skipped", extra={"rec_id": r.id, "doc_id": r.doc_id})
                    continue
            conn.commit()
        
        logger.info(f"Saved {len(recommendations)} recommendations to {self.db_path}")
    
    async def get_by_filters(
        self,
        bank: Optional[str] = None,
        asset_class: Optional[str] = None,
        doc_id: Optional[str] = None,
        source_type: Optional[str] = None,
        is_active: Optional[bool] = None
    ) -> List[InternalView]: # Return extended model capable of holding extra fields
        """Get recommendations matching optional filters."""
        query = "SELECT * FROM recommendations WHERE 1=1"
        params: List[Any] = []
        
        if bank:
            query += " AND bank LIKE ?"
            params.append(f"%{bank}%")
        if asset_class:
            query += " AND asset_class LIKE ?"
            params.append(f"%{asset_class}%")
        if doc_id:
            query += " AND doc_id = ?"
            params.append(doc_id)
        if source_type:
            query += " AND source_type = ?"
            params.append(source_type)
        if is_active is not None:
            query += " AND is_active = ?"
            params.append(1 if is_active else 0)
            
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            recommendations: List[InternalView] = []
            for row in rows:
                try:
                    recommendations.append(_row_to_internal_view(row))
                except Exception as e:
                    row_id = row["id"] if "id" in row.keys() else None
                    logger.warning("Failed to parse recommendation row", exc_info=True, extra={"row_id": row_id})
                    continue
            
            return recommendations
    
    async def get_all(self) -> List[Recommendation]:
        """Get all stored recommendations."""
        return await self.get_by_filters()

    def delete_by_doc_id(self, doc_id: str) -> int:
        """Delete all recommendations for a document."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM recommendations WHERE doc_id = ?",
                (doc_id,)
            )
            conn.commit()
            deleted_count = cursor.rowcount
            logger.info(f"Deleted {deleted_count} recommendations for doc_id={doc_id}")
            return deleted_count


def _split_long_markdown_block(block: str, max_chars: int) -> List[str]:
    """Split a single oversized markdown block without dropping content."""
    parts: List[str] = []
    remaining = block.strip()

    while len(remaining) > max_chars:
        split_at = max(
            remaining.rfind("\n", 0, max_chars),
            remaining.rfind(". ", 0, max_chars),
            remaining.rfind(" ", 0, max_chars),
        )
        if split_at < max_chars // 2:
            split_at = max_chars

        part = remaining[:split_at].strip()
        if part:
            parts.append(part)
        remaining = remaining[split_at:].strip()

    if remaining:
        parts.append(remaining)

    return parts


def _split_markdown_for_recommendation_extraction(
    raw_markdown: str,
    max_chars: int = RECOMMENDATION_EXTRACTION_MAX_CHARS,
) -> List[str]:
    """Split report markdown into bounded extraction windows."""
    blocks = [block.strip() for block in raw_markdown.split("\n\n") if block.strip()]
    if not blocks:
        return []

    windows: List[str] = []
    current_blocks: List[str] = []
    current_length = 0

    def flush_current() -> None:
        nonlocal current_blocks, current_length
        if not current_blocks:
            return
        window = "\n\n".join(current_blocks).strip()
        if window:
            windows.append(window)
        current_blocks = []
        current_length = 0

    for block in blocks:
        if len(block) > max_chars:
            flush_current()
            windows.extend(_split_long_markdown_block(block, max_chars))
            continue

        separator_length = 2 if current_blocks else 0
        projected_length = current_length + separator_length + len(block)
        if current_blocks and projected_length > max_chars:
            flush_current()
            projected_length = len(block)

        current_blocks.append(block)
        current_length = projected_length

    flush_current()
    return windows


def _normalise_recommendation_key(value: Optional[str]) -> str:
    return " ".join(str(value or "").lower().split())


def _dedupe_recommendations(recommendations: List[Recommendation]) -> List[Recommendation]:
    """Deduplicate recommendations extracted from neighboring report windows."""
    deduped: Dict[Tuple[str, str, str, str], Recommendation] = {}

    for recommendation in recommendations:
        key = (
            _normalise_recommendation_key(recommendation.asset_class),
            _normalise_recommendation_key(recommendation.sub_asset),
            _normalise_recommendation_key(recommendation.stance),
            _normalise_recommendation_key(recommendation.horizon),
        )
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = recommendation
            continue

        if existing.page is None and recommendation.page is not None:
            existing.page = recommendation.page
        if existing.section is None and recommendation.section is not None:
            existing.section = recommendation.section
        if existing.confidence is None and recommendation.confidence is not None:
            existing.confidence = recommendation.confidence

    return list(deduped.values())


async def extract_recommendations_with_mistral(
    doc_id: str,
    bank: str,
    raw_markdown: str,
) -> List[Recommendation]:
    """
    Use Mistral Chat API to extract structured investment recommendations
    from research report markdown.
    """
    if not settings.MISTRAL_API_KEY:
        logger.warning("MISTRAL_API_KEY not set, skipping recommendation extraction")
        return []

    from services.prompt_loader import load_prompt
    from services.llm_client import get_llm_client

    system_prompt = load_prompt("recommendations_system")
    markdown_windows = _split_markdown_for_recommendation_extraction(raw_markdown)
    if not markdown_windows:
        return []

    if len(markdown_windows) > 1:
        logger.info(
            "Split recommendation extraction into %s windows for document %s",
            len(markdown_windows),
            doc_id,
        )

    try:
        client = get_llm_client()
        recommendations: List[Recommendation] = []

        for window_index, markdown_text in enumerate(markdown_windows, start=1):
            user_prompt = load_prompt(
                "recommendations_user",
                bank=bank,
                markdown_text=markdown_text,
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

            parsed = await client.get_chat_completion(
                messages=messages,
                json_mode=True,
            )

            # Handle different response structures
            raw_recommendations = parsed.get("recommendations", [])
            if not isinstance(raw_recommendations, list):
                raw_recommendations = [raw_recommendations] if raw_recommendations else []

            for r in raw_recommendations:
                if not isinstance(r, dict):
                    continue
                try:
                    recommendations.append(
                        Recommendation(
                            id=str(uuid.uuid4()),
                            doc_id=doc_id,
                            bank=bank,
                            source_type="sell_side",
                            asset_class=str(r.get("asset_class", "other")).lower(),
                            sub_asset=r.get("sub_asset"),
                            stance=str(r.get("stance", "Neutral")),
                            horizon=r.get("horizon"),
                            rationale=str(r.get("rationale", "")),
                            page=r.get("page"),
                            section=r.get("section"),
                            confidence=r.get("confidence"),
                        )
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to parse recommendation from LLM response",
                        exc_info=True,
                        extra={"doc_id": doc_id, "window_index": window_index},
                    )
                    continue

        deduped = _dedupe_recommendations(recommendations)
        logger.info(
            "Extracted %s recommendations from document %s across %s windows",
            len(deduped),
            doc_id,
            len(markdown_windows),
        )
        return deduped

    except Exception:
        logger.error("Recommendation extraction failed", exc_info=True, extra={"doc_id": doc_id, "bank": bank})
        raise


# Singleton instance
_recommendation_store: Optional[RecommendationStore] = None


def get_recommendation_store() -> RecommendationStore:
    """Get or create the recommendation store singleton."""
    global _recommendation_store
    if _recommendation_store is None:
        _recommendation_store = RecommendationStore()
    return _recommendation_store
