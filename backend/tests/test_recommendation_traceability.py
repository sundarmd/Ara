import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import main
from models.schemas import Recommendation
from services.recommendations import RecommendationStore


class RecommendationTraceabilityTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_and_get_preserves_page_section_and_confidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RecommendationStore(db_path=os.path.join(tmpdir, "recommendations.db"))
            recommendation = Recommendation(
                id="rec-1",
                doc_id="doc-1",
                bank="GS",
                source_type="sell_side",
                asset_class="multi_asset",
                sub_asset="EM local rates",
                stance="Long",
                horizon="3m",
                rationale="Fed cuts support EM duration.",
                page=9,
                section="EM - Supportive Backdrop",
                confidence="high",
                date="2025-08-18",
            )

            await store.save_recommendations([recommendation])
            saved = await store.get_by_filters(doc_id="doc-1")

        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].page, 9)
        self.assertEqual(saved[0].section, "EM - Supportive Backdrop")
        self.assertEqual(saved[0].confidence, "high")

    async def test_debug_recommendations_exposes_traceability_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RecommendationStore(db_path=os.path.join(tmpdir, "recommendations.db"))
            recommendation = Recommendation(
                id="rec-1",
                doc_id="doc-1",
                bank="GS",
                source_type="sell_side",
                asset_class="multi_asset",
                sub_asset="EM local rates",
                stance="Long",
                horizon="3m",
                rationale="Fed cuts support EM duration.",
                page=9,
                section="EM - Supportive Backdrop",
                confidence="high",
                date="2025-08-18",
            )
            await store.save_recommendations([recommendation])

            with patch.object(main, "get_recommendation_store", return_value=store):
                response = await main.debug_recommendations(
                    bank=None,
                    asset_class=None,
                    doc_id="doc-1",
                    source_type=None,
                )

        self.assertEqual(response["count"], 1)
        recommendation_payload = response["recommendations"][0]
        self.assertEqual(recommendation_payload["page"], 9)
        self.assertEqual(recommendation_payload["section"], "EM - Supportive Backdrop")
        self.assertEqual(recommendation_payload["confidence"], "high")

    async def test_existing_schema_migration_adds_traceability_columns(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "recommendations.db")
            with sqlite3.connect(db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE recommendations (
                        id TEXT PRIMARY KEY,
                        doc_id TEXT,
                        source_type TEXT,
                        bank TEXT,
                        asset_class TEXT,
                        sub_asset TEXT,
                        ticker TEXT,
                        stance TEXT,
                        time_horizon TEXT,
                        rationale TEXT,
                        date TEXT,
                        analyst_id TEXT,
                        is_active INTEGER DEFAULT 1,
                        outcome TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO recommendations
                    (id, doc_id, source_type, bank, asset_class, sub_asset,
                     ticker, stance, time_horizon, rationale, date,
                     analyst_id, is_active, outcome)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "rec-old",
                        "doc-old",
                        "sell_side",
                        "GS",
                        "multi_asset",
                        "EM local rates",
                        None,
                        "Long",
                        "12m",
                        "Legacy horizon value.",
                        "2025-08-17",
                        None,
                        1,
                        None,
                    ),
                )
                conn.commit()

            store = RecommendationStore(db_path=db_path)
            with sqlite3.connect(db_path) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(recommendations)")}

            self.assertIn("horizon", columns)
            self.assertNotIn("time_horizon", columns)
            self.assertIn("page", columns)
            self.assertIn("section", columns)
            self.assertIn("confidence", columns)

            legacy_saved = await store.get_by_filters(doc_id="doc-old")
            self.assertEqual(legacy_saved[0].horizon, "12m")

            recommendation = Recommendation(
                id="rec-1",
                doc_id="doc-1",
                bank="GS",
                source_type="sell_side",
                asset_class="multi_asset",
                sub_asset="EM local rates",
                stance="Long",
                horizon="3m",
                rationale="Fed cuts support EM duration.",
                page=9,
                section="EM - Supportive Backdrop",
                confidence="high",
                date="2025-08-18",
            )
            await store.save_recommendations([recommendation])
            saved = await store.get_by_filters(doc_id="doc-1")

        self.assertEqual(saved[0].page, 9)
        self.assertEqual(saved[0].section, "EM - Supportive Backdrop")
        self.assertEqual(saved[0].confidence, "high")
