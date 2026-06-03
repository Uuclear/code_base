"""三端字段映射单元测试。"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.field_map import fields_from_scrape  # noqa: E402

LIMIS_JSON = Path(__file__).resolve().parents[2] / "ScanReport" / "output" / "test_1_2" / "1.json"


class TestFieldMapLimis(unittest.TestCase):
    @unittest.skipUnless(LIMIS_JSON.is_file(), "需要 ScanReport/output/test_1_2/1.json")
    def test_limis_sample_and_date(self) -> None:
        scrape = json.loads(LIMIS_JSON.read_text(encoding="utf-8"))
        f = fields_from_scrape(scrape, "limis")
        self.assertEqual(f["sample_name"], "拌合用水")
        self.assertTrue(f["report_date"])
        self.assertIn("浦东", f["project_name"])
        self.assertEqual(f["order_no"], "HX18-260001")
        self.assertEqual(f["report_no"], "HX188-260007")


class TestFieldMapAssociation(unittest.TestCase):
    def test_empty_project_returns_blank(self) -> None:
        f = fields_from_scrape({"project": {}, "samples": []}, "association")
        self.assertEqual(f["project_name"], "")

    def test_filled_association(self) -> None:
        scrape = {
            "qr_content": "HN01-1|110807184827",
            "project": {
                "consign_no": "2026054863",
                "report_no": "HN01-202629448",
                "project_name": "金谷项目",
                "project_section": "二期",
                "report_date": "2026/6/1",
                "anti_fake_code": "110807184827",
            },
            "samples": [{"sample_name": "混凝土立方体试件"}],
        }
        f = fields_from_scrape(scrape, "association")
        self.assertEqual(f["order_no"], "2026054863")
        self.assertEqual(f["sample_name"], "混凝土立方体试件")
        self.assertEqual(f["section"], "二期")


if __name__ == "__main__":
    unittest.main()
