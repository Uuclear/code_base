"""日期格式化。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.date_format import format_report_date, parse_report_date_key  # noqa: E402


class TestDateFormat(unittest.TestCase):
    def test_variants(self) -> None:
        self.assertEqual(format_report_date("2026/6/1"), "2026-06-01")
        self.assertEqual(format_report_date("2026-01-19"), "2026-01-19")
        self.assertEqual(parse_report_date_key("2026/6/1"), 20260601)


if __name__ == "__main__":
    unittest.main()
