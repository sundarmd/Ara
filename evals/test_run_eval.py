import unittest

from evals.run_eval import check_case


class EvalCitationCheckTests(unittest.TestCase):
    def test_answer_must_have_citations_requires_matching_source_id(self):
        result = check_case(
            {
                "id": "requires-citation",
                "expect": {
                    "min_sources": 1,
                    "answer_must_have_citations": True,
                },
            },
            {
                "answer": "Duration is attractive without a citation.",
                "sources": [{"citation_id": 1}],
            },
        )

        self.assertFalse(result.passed)
        self.assertEqual(
            result.failures,
            ["answer missing citation matching returned source IDs"],
        )

    def test_answer_must_have_citations_accepts_matching_source_id(self):
        result = check_case(
            {
                "id": "has-citation",
                "expect": {
                    "min_sources": 1,
                    "answer_must_have_citations": True,
                },
            },
            {
                "answer": "Duration is attractive [100].",
                "sources": [{"citation_id": 100}],
            },
        )

        self.assertTrue(result.passed)
        self.assertEqual(result.failures, [])

    def test_answer_must_have_citations_rejects_unknown_citation_id(self):
        result = check_case(
            {
                "id": "wrong-citation",
                "expect": {
                    "min_sources": 1,
                    "answer_must_have_citations": True,
                },
            },
            {
                "answer": "Duration is attractive [999].",
                "sources": [{"citation_id": 1}],
            },
        )

        self.assertFalse(result.passed)
        self.assertEqual(
            result.failures,
            ["answer missing citation matching returned source IDs"],
        )


if __name__ == "__main__":
    unittest.main()
