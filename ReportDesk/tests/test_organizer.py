"""Unit tests for path organizer and file index (no GUI / network)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.constants import NO_SECTION  # noqa: E402
from core.organizer import (  # noqa: E402
    build_dest_dir,
    build_stored_filename,
    sanitize_path_component,
)
from db.repository import Repository  # noqa: E402


class TestOrganizer(unittest.TestCase):
    def test_sanitize_invalid_chars(self) -> None:
        self.assertEqual(sanitize_path_component('a/b*c'), "a_b_c")

    def test_section_dash(self) -> None:
        self.assertEqual(sanitize_path_component("-", fallback=NO_SECTION), NO_SECTION)

    def test_stored_filename(self) -> None:
        self.assertEqual(
            build_stored_filename("JG018-250187", 1, Path("x.JPG")),
            "JG018-250187-1.jpg",
        )

    def test_build_dest_dir_with_section(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = build_dest_dir(Path(td), "工程A", "标段1")
            parts = d.parts
            self.assertIn("报告", parts)
            self.assertIn("工程A", parts)
            self.assertIn("标段1", parts)

    def test_build_dest_dir_without_section(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = build_dest_dir(Path(td), "工程A", None)
            self.assertEqual(d, Path(td) / "报告" / "工程A")
            d2 = build_dest_dir(Path(td), "工程A", NO_SECTION)
            self.assertEqual(d2, Path(td) / "报告" / "工程A")

    def test_allocate_file_index(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "t.db"
            repo = Repository.open(str(db))
            try:
                repo.upsert_report(
                    {
                        "report_no": "TEST-001",
                        "source_channel": "limis",
                        "decode_method": "ocr",
                        "scrape_status": "partial",
                        "section_folder": None,
                    }
                )
                self.assertEqual(repo.allocate_file_index("TEST-001"), 1)
                repo.insert_report_file("TEST-001", 1, "/a.jpg", None, "a.jpg")
                self.assertEqual(repo.allocate_file_index("TEST-001"), 2)
            finally:
                repo.conn.close()


if __name__ == "__main__":
    unittest.main()
