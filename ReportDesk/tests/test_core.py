"""Unit checks for normalize helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.constants import SECTION_NONE  # noqa: E402
from core.normalize import (  # noqa: E402
    normalize_from_scrape,
    normalize_report_no,
    section_folder_for_association,
)
from core.pipeline import report_no_from_scrape  # noqa: E402


class TestReportNo(unittest.TestCase):
    def test_uppercase(self) -> None:
        self.assertEqual(normalize_report_no("hx188-260007"), "HX188-260007")


class TestSectionFolder(unittest.TestCase):
    def test_association_dash(self) -> None:
        self.assertIsNone(section_folder_for_association("-"))
        self.assertEqual(section_folder_for_association("一标段"), "一标段")


class TestReportNoFromScrape(unittest.TestCase):
    def test_institute_uses_r_no(self) -> None:
        scrape = {
            "query": {"r_no": "FS188-250078"},
            "project": {"report_no": "FS188-250078"},
        }
        self.assertEqual(
            report_no_from_scrape(scrape, "institute"),
            "FS188-250078",
        )


class TestAssociationBundle(unittest.TestCase):
    def test_section_and_part(self) -> None:
        data = {
            "project": {
                "report_no": "lx3s-202600055",
                "project_name": "测试工程",
                "project_section": "-",
            },
            "samples": [{"project_part": "部位A"}],
            "scraped_at": "2026-01-01",
        }
        bundle = normalize_from_scrape(
            data,
            report_no="lx3s-202600055",
            source_channel="association",
            decode_method="qr",
            source_image="x.jpg",
        )
        self.assertEqual(bundle["report"]["report_no"], "LX3S-202600055")
        self.assertIsNone(bundle["report"]["section_folder"])
        self.assertEqual(bundle["report"]["project_part"], "部位A")


if __name__ == "__main__":
    unittest.main()
