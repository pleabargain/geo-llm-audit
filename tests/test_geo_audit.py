import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import geo_audit


class TestNormalizeUrl(unittest.TestCase):
    def test_adds_https(self):
        self.assertEqual(geo_audit.normalize_url("example.com"), "https://example.com")
    def test_keeps_scheme(self):
        self.assertEqual(geo_audit.normalize_url("http://example.com"), "http://example.com")
    def test_strips_whitespace(self):
        self.assertEqual(geo_audit.normalize_url("  example.com  "), "https://example.com")
    def test_empty(self):
        self.assertEqual(geo_audit.normalize_url(""), "")


class TestBuildHtmlReport(unittest.TestCase):
    def setUp(self):
        self.report = {
            "url": "https://example.com",
            "score": 70,
            "checks": {
                "robots_txt": {"exists": True, "blocks_ai": False, "content": None},
                "sitemap": {"exists": True},
                "llms_txt": {"exists": False, "content": None},
                "homepage": {
                    "title": "Example", "meta_description": "desc", "h1": ["Hi"],
                    "schema_types": ["Organization"], "schema_count": 1,
                    "images_total": 2, "images_missing_alt": 1,
                    "images_missing_alt_list": ["https://example.com/img.png"],
                    "images_all_list": ["https://example.com/img.png"],
                    "platform_guess": "WordPress", "word_count": 100,
                },
                "ai_mentions": {},
            },
            "recommendations": ["Add llms.txt", "Add alt text"],
        }

    def test_contains_title(self):
        html = geo_audit.build_html_report(self.report)
        self.assertIn("example.com", html)
    def test_contains_score(self):
        html = geo_audit.build_html_report(self.report)
        self.assertIn("70/100", html)
    def test_contains_recommendations(self):
        html = geo_audit.build_html_report(self.report)
        self.assertIn("Recommendations to improve score", html)
        self.assertIn("Add llms.txt", html)
    def test_report_view_alias(self):
        self.assertIs(geo_audit.report_view, geo_audit.build_html_report)


class TestBuildRecommendations(unittest.TestCase):
    def test_repcee_like(self):
        checks = {
            "robots_txt": {"exists": True, "blocks_ai": False},
            "sitemap": {"exists": True},
            "llms_txt": {"exists": True},
            "homepage": {"title": "t", "meta_description": "d", "h1": [], "schema_count": 1,
                        "images_missing_alt": 2, "word_count": 257},
            "ai_mentions": {"openai": "error: 'choices'"},
        }
        recs = geo_audit.build_recommendations(checks)
        self.assertIn("Add a clear H1 heading to the homepage.", recs)
        self.assertIn("Add alt text to 2 image(s) missing it.", recs)
        self.assertTrue(any("substantive homepage content" in r for r in recs))
        self.assertTrue(any("Fix openai API access" in r for r in recs))
    def test_perfect_site(self):
        checks = {
            "robots_txt": {"exists": True, "blocks_ai": False},
            "sitemap": {"exists": True},
            "llms_txt": {"exists": True},
            "homepage": {"title": "t", "meta_description": "d", "h1": ["h"], "schema_count": 1,
                        "images_missing_alt": 0, "word_count": 400},
            "ai_mentions": {},
        }
        recs = geo_audit.build_recommendations(checks)
        # only ai mentions missing
        self.assertEqual(recs, ["Set OPENAI_API_KEY / ANTHROPIC_API_KEY to test AI brand mentions."])


if __name__ == "__main__":
    unittest.main()
