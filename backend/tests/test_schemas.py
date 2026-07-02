import unittest

from pydantic import ValidationError

from models.schemas import ErrorEvent, Recommendation, Segment


class SchemaTests(unittest.TestCase):
    def test_segment_rejects_unknown_segment_type(self):
        with self.assertRaises(ValidationError):
            Segment(
                doc_id="doc-1",
                page=1,
                segment_type="chart",
                text="Invalid segment type",
            )

    def test_recommendation_preserves_traceability_fields(self):
        recommendation = Recommendation(
            id="rec-1",
            doc_id="doc-1",
            bank="GS",
            source_type="sell_side",
            asset_class="rates",
            sub_asset="US duration",
            stance="Long",
            horizon="3m",
            rationale="Curve steepening supports duration.",
            page=8,
            section="Rates Strategy",
            confidence="medium",
        )

        self.assertEqual(recommendation.page, 8)
        self.assertEqual(recommendation.section, "Rates Strategy")
        self.assertEqual(recommendation.confidence, "medium")

    def test_error_event_accepts_machine_readable_code(self):
        event = ErrorEvent(message="Provider failed", code="chat_error")

        self.assertEqual(event.type, "error")
        self.assertEqual(event.code, "chat_error")
