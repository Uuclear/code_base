"""JSON association path: mock API responses (no real report required)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parse_association_api import RPTVERIFY_API, SIGNBOARD_API
from src.qr_decode import DecodeResult
from src.scrape_association import scrape_association


class TestAssociationJsonMock(unittest.TestCase):
    def test_rptverify_success_end_to_end(self):
        decode = DecodeResult(
            image="mock.jpg",
            qr_texts=["RPT-202600001|012345678901"],
            report_type="association",
            report_no="RPT-202600001",
            anti_fake_code="012345678901",
        )
        fake_api = {
            "resultCode": 200,
            "data": {"reportUrl": "https://cdn.example.com/report.pdf"},
        }

        with patch(
            "src.scrape_association.fetch_rptverify_json",
            return_value=fake_api,
        ) as fetch_mock:
            out = scrape_association(decode)

        fetch_mock.assert_called_once()
        self.assertEqual(out["query"]["backend"], "rptverify_json")
        self.assertEqual(out["query"]["endpoint"], RPTVERIFY_API)
        self.assertEqual(
            out["report_pdf_url"],
            "https://cdn.example.com/report.pdf",
        )
        self.assertEqual(
            out["project"]["report_pdf_url"],
            "https://cdn.example.com/report.pdf",
        )

    def test_signboard_success_end_to_end(self):
        decode = DecodeResult(
            image="mock.jpg",
            qr_texts=["SB-202600001|300112345678"],
            report_type="association",
            report_no="SB-202600001",
            anti_fake_code="300112345678",
        )
        fake_api = {
            "code": 200,
            "data": {"reportUrl": "https://signboard.example.com/r.pdf"},
        }

        with patch(
            "src.scrape_association.fetch_signboard_json",
            return_value=fake_api,
        ):
            out = scrape_association(decode)

        self.assertEqual(out["query"]["backend"], "signboard_json")
        self.assertEqual(out["query"]["endpoint"], SIGNBOARD_API)

    def test_rptverify_api_rejection_raises(self):
        decode = DecodeResult(
            image="mock.jpg",
            qr_texts=["RPT-202600001|012345678901"],
            report_type="association",
            report_no="RPT-202600001",
            anti_fake_code="012345678901",
        )
        with patch(
            "src.scrape_association.fetch_rptverify_json",
            return_value={"resultCode": 60025, "resultMessage": "编号或校验码错误"},
        ):
            with self.assertRaises(ValueError) as ctx:
                scrape_association(decode)
        self.assertIn("rptverify API", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
