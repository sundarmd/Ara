import unittest
from unittest.mock import patch

from services import recommendations


class RecordingLLMClient:
    def __init__(self):
        self.user_prompts = []

    async def get_chat_completion(self, messages, json_mode=False):
        user_prompt = next(message["content"] for message in messages if message["role"] == "user")
        self.user_prompts.append(user_prompt)

        extracted = []
        if "EARLY_RECOMMENDATION" in user_prompt:
            extracted.append(
                {
                    "asset_class": "rates",
                    "sub_asset": "US duration",
                    "stance": "Long",
                    "horizon": "3m",
                    "rationale": "EARLY_RECOMMENDATION: policy easing supports duration.",
                    "page": 2,
                    "section": "Rates",
                    "confidence": "high",
                }
            )
        if "LATE_RECOMMENDATION" in user_prompt:
            extracted.append(
                {
                    "asset_class": "fx",
                    "sub_asset": "JPY",
                    "stance": "Long",
                    "horizon": "6m",
                    "rationale": "LATE_RECOMMENDATION: valuation and policy divergence support JPY.",
                    "page": 41,
                    "section": "FX",
                    "confidence": "medium",
                }
            )
        return {"recommendations": extracted}


class RecommendationExtractionTests(unittest.IsolatedAsyncioTestCase):
    async def test_extracts_recommendations_after_first_20000_characters(self):
        client = RecordingLLMClient()
        raw_markdown = "\n\n".join(
            [
                "# Rates\nEARLY_RECOMMENDATION: Long US duration for 3m.",
                "Filler paragraph. " * 1500,
                "# FX\nLATE_RECOMMENDATION: Long JPY for 6m.",
            ]
        )

        with (
            patch.object(recommendations.settings, "MISTRAL_API_KEY", "test-key"),
            patch("services.llm_client.get_llm_client", return_value=client),
        ):
            extracted = await recommendations.extract_recommendations_with_mistral(
                doc_id="doc-1",
                bank="GS",
                raw_markdown=raw_markdown,
            )

        sub_assets = {recommendation.sub_asset for recommendation in extracted}
        self.assertEqual(sub_assets, {"US duration", "JPY"})
        self.assertGreaterEqual(len(client.user_prompts), 2)
        self.assertTrue(any("LATE_RECOMMENDATION" in prompt for prompt in client.user_prompts))
        self.assertEqual(extracted[1].page, 41)
        self.assertEqual(extracted[1].section, "FX")
        self.assertEqual(extracted[1].confidence, "medium")

    async def test_deduplicates_recommendations_across_windows(self):
        client = RecordingLLMClient()
        raw_markdown = "\n\n".join(
            [
                "# Rates\nEARLY_RECOMMENDATION: Long US duration for 3m.",
                "Filler paragraph. " * 1500,
                "# Rates recap\nEARLY_RECOMMENDATION: Long US duration for 3m.",
            ]
        )

        with (
            patch.object(recommendations.settings, "MISTRAL_API_KEY", "test-key"),
            patch("services.llm_client.get_llm_client", return_value=client),
        ):
            extracted = await recommendations.extract_recommendations_with_mistral(
                doc_id="doc-1",
                bank="GS",
                raw_markdown=raw_markdown,
            )

        self.assertEqual(len(extracted), 1)
        self.assertEqual(extracted[0].sub_asset, "US duration")
