import unittest

from server import recommend_priority


class PriorityRecommendationTests(unittest.TestCase):
    def test_explicit_immediate_risk_is_critical(self):
        result = recommend_priority("Live wire on road", "A live wire is hanging over the footpath", "Roads & Potholes")
        self.assertEqual(result["priority"], "Critical")
        self.assertTrue(result["priorityReason"])

    def test_essential_service_raises_baseline(self):
        result = recommend_priority("Water supply issue", "Water supply has stopped in the locality", "Water Supply")
        self.assertIn(result["priority"], ("Medium", "High", "Critical"))

    def test_neutral_report_is_low(self):
        result = recommend_priority("Broken park bench", "A bench is damaged in the park", "Public Infrastructure")
        self.assertEqual(result["priority"], "Low")

    def test_recommendation_contains_explanation(self):
        result = recommend_priority("Pothole", "There is a pothole near the market", "Roads & Potholes")
        self.assertGreaterEqual(result["priorityScore"], 0)
        self.assertTrue(result["priorityReason"])


if __name__ == "__main__":
    unittest.main()
