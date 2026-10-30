import sys
from datetime import date
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import seo_traffic_report as report

class PrivateSeoReportTests(TestCase):
    def test_no_credentials_is_not_zero_traffic(self):
        result = report.collect({}, date(2026, 10, 30))
        self.assertEqual((result["start"], result["end"]), ("2026-09-30", "2026-10-27"))
        self.assertTrue(all(x["status"] == "authorization_required" for x in result["sources"].values()))
        self.assertNotIn("clicks", result["sources"]["bing"])

    def test_google_search_console_rows(self):
        def fake(url, payload=None, token=None):
            if not payload.get("dimensions"):
                return {"rows": [{"clicks": 4, "impressions": 72}]}
            if payload["dimensions"] == ["query"]:
                return {"rows": [{"keys": ["ai receptionist"], "clicks": 3, "impressions": 40}]}
            return {"rows": []}
        with patch.object(report, "request_json", side_effect=fake):
            result = report.gsc_report("token", "2026-09-30", "2026-10-27")
        self.assertEqual(result["clicks"], 4)
        self.assertEqual(result["queries"][0]["name"], "ai receptionist")

    def test_ga4_requires_numeric_id(self):
        with self.assertRaises(RuntimeError):
            report.ga4_report("token", "G-129XGJDT47", "2026-09-30", "2026-10-27")

    def test_bing_date_and_private_query(self):
        self.assertEqual(report.bing_date("/Date(1316156400000-0700)/"), "2011-09-16")
        def fake(url, payload=None, token=None):
            if "GetRankAndTrafficStats" in url:
                return {"d": [{"Date": "2026-10-01", "Clicks": 2, "Impressions": 50},
                              {"Date": "2026-07-01", "Clicks": 100, "Impressions": 150}]}
            return {"d": [{"Date": "2026-10-01", "Query": "plumbers", "Clicks": 1, "Impressions": 10}]}
        with patch.object(report, "request_json", side_effect=fake):
            result = report.bing_report("abcdefghijklmnop", "2026-09-30", "2026-10-27")
        self.assertEqual(result["clicks"], 2)
        self.assertEqual(result["queries"][0]["query"], "plumbers")

    def test_no_api_calls_to_unauthorized_hosts(self):
        with self.assertRaises(ValueError):
            report.request_json("https://example.org/leak")

    def test_markdown_does_not_fabricate_metrics(self):
        result = report.to_markdown(report.collect({}, date(2026, 10, 30)))
        self.assertIn("authorization_required", result)
        self.assertIn("do not commit", result)
        self.assertNotIn("Clicks: 0", result)
