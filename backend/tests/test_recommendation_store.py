import os
import sqlite3
import tempfile
import unittest

from models.schemas import Recommendation
from services.recommendations import RecommendationStore


class RecommendationStoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_save_filter_and_delete_recommendations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = RecommendationStore(db_path=os.path.join(tmpdir, "recommendations.db"))
            await store.save_recommendations([
                Recommendation(
                    id="rec-1",
                    doc_id="doc-1",
                    bank="GS",
                    source_type="sell_side",
                    asset_class="rates",
                    sub_asset="US duration",
                    stance="Long",
                    horizon="3m",
                    rationale="Soft landing supports duration.",
                    page=4,
                    section="Duration",
                    confidence="high",
                    date="2026-01-01",
                ),
                Recommendation(
                    id="rec-2",
                    doc_id="doc-2",
                    bank="JPM",
                    source_type="sell_side",
                    asset_class="equity",
                    sub_asset="US tech",
                    stance="Overweight",
                    horizon="12m",
                    rationale="Earnings revisions remain supportive.",
                    date="2026-01-02",
                ),
            ])

            rates = await store.get_by_filters(asset_class="rates")
            deleted_count = store.delete_by_doc_id("doc-1")
            remaining = await store.get_all()
            with sqlite3.connect(store.db_path) as conn:
                columns = {row[1] for row in conn.execute("PRAGMA table_info(recommendations)")}

        self.assertEqual([recommendation.id for recommendation in rates], ["rec-1"])
        self.assertEqual(rates[0].page, 4)
        self.assertEqual(rates[0].horizon, "3m")
        self.assertIn("horizon", columns)
        self.assertNotIn("time_horizon", columns)
        self.assertEqual(deleted_count, 1)
        self.assertEqual([recommendation.id for recommendation in remaining], ["rec-2"])
