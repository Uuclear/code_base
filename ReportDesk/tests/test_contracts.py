"""合同表与目录上级文件夹。"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.contract_paths import (  # noqa: E402
    FOLDER_PARENT_HANDLER,
    FOLDER_PARENT_MANAGER,
    resolve_parent_folder_name,
)
from core.organizer import build_dest_dir  # noqa: E402
from db.repository import Repository  # noqa: E402


class TestContracts(unittest.TestCase):
    def test_exact_match_only(self) -> None:
        def lookup(name: str):
            if name == "工程A":
                return {"manager": "张三", "handler": "李四"}
            return None

        self.assertEqual(
            resolve_parent_folder_name("工程A", FOLDER_PARENT_MANAGER, lookup),
            "张三",
        )
        # 首尾空白会 trim 后匹配；中间字符须一致
        self.assertEqual(
            resolve_parent_folder_name("  工程A  ", FOLDER_PARENT_MANAGER, lookup),
            "张三",
        )
        self.assertIsNone(resolve_parent_folder_name("工程A1", FOLDER_PARENT_MANAGER, lookup))
        self.assertEqual(
            resolve_parent_folder_name("工程A", FOLDER_PARENT_HANDLER, lookup),
            "李四",
        )

    def test_build_dest_with_parent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = build_dest_dir(
                Path(td),
                "工程A",
                None,
                folder_parent_mode=FOLDER_PARENT_MANAGER,
                contract_lookup=lambda n: {"manager": "王五"} if n == "工程A" else None,
            )
            self.assertEqual(d, Path(td) / "报告" / "王五" / "工程A")

    def test_repo_import(self) -> None:
        from db.import_contracts import read_contract_rows

        xlsx = Path(__file__).resolve().parents[1].parent.parent / "合同.xlsx"
        if not xlsx.is_file():
            self.skipTest("合同.xlsx 不在仓库根目录")
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "t.db"
            repo = Repository.open(str(db))
            try:
                n = repo.import_project_contracts_from_excel(xlsx)
                self.assertGreater(n, 0)
                sample = read_contract_rows(xlsx)[0]["project_name"]
                self.assertIsNotNone(repo.lookup_project_contract(sample))
            finally:
                repo.close()


if __name__ == "__main__":
    unittest.main()
