"""OCR 与二维码字段分离。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.field_map import fields_from_decode, fields_from_scrape  # noqa: E402


class TestOcrFieldSeparation(unittest.TestCase):
    def test_decode_ocr_not_in_qr(self) -> None:
        f = fields_from_decode(
            qr_content="HN01-1|110807184827",
            ocr_preview="整页OCR文字",
            decode_method="ocr",
        )
        self.assertEqual(f["qr_content"], "")
        self.assertIn("整页OCR", f["ocr_content"])

    def test_decode_qr_only_in_qr(self) -> None:
        f = fields_from_decode(
            qr_content="http://example.com?q=1",
            decode_method="qr",
        )
        self.assertIn("example.com", f["qr_content"])
        self.assertEqual(f["ocr_content"], "")

    def test_scrape_limis_ocr_in_ocr_box(self) -> None:
        scrape = {
            "report_type": "limis",
            "identification": {"method": "ocr", "ocr_text_preview": "报告编号:HX188"},
            "qr_content": "报告编号:HX188",
            "match": {"testingReportNo": "HX188-260007"},
            "integrated_list_row": {"projectName": "工程A"},
            "detail": {"tasks": [{"sampleName": "水"}]},
        }
        f = fields_from_scrape(scrape, "limis")
        self.assertEqual(f["qr_content"], "")
        self.assertIn("HX188", f["ocr_content"])


if __name__ == "__main__":
    unittest.main()
