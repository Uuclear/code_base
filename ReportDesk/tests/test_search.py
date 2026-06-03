"""报告库搜索。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from db.connection import get_connection  # noqa: E402
from db.repository import Repository  # noqa: E402


class TestSearch(unittest.TestCase):
    def test_fuzzy_project_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            repo = Repository(get_connection(str(db)))
            repo.upsert_report(
                {
                    "report_no": "HX188-260007",
                    "source_channel": "limis",
                    "order_no": "HX18-260001",
                    "project_name": "浦东机场工程",
                    "report_date": "2026-01-19",
                }
            )
            repo.replace_samples(
                "HX188-260007",
                [{"sample_name": "拌合用水"}],
            )
            rows = repo.search_reports(project_name="浦东", sample_name="拌合")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["report_no"], "HX188-260007")
            repo.close()


if __name__ == "__main__":
    unittest.main()
