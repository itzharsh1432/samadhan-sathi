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


class EvidenceImageDataUrlTests(unittest.TestCase):
    def test_accepts_bounded_jpeg_data_url(self):
        import base64
        from server import decode_image_data_url

        sample = bytes([255, 216, 255]) + b"test-photo-bytes" + bytes([255, 217])
        encoded = "data:image/jpeg;base64," + base64.b64encode(sample).decode("ascii")
        self.assertEqual(decode_image_data_url(encoded), sample)

    def test_rejects_non_jpeg_data_url(self):
        from server import decode_image_data_url

        with self.assertRaises(ValueError):
            decode_image_data_url("data:image/png;base64,aW52YWxpZA==")

    def test_rejects_invalid_jpeg_signature(self):
        import base64
        from server import decode_image_data_url

        encoded = "data:image/jpeg;base64," + base64.b64encode(b"not-a-jpeg").decode("ascii")
        with self.assertRaises(ValueError):
            decode_image_data_url(encoded)

    def test_rejects_oversized_data_url(self):
        from server import decode_image_data_url

        with self.assertRaises(ValueError):
            decode_image_data_url("x" * 3_000_001)


if __name__ == "__main__":
    unittest.main()
