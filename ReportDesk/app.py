#!/usr/bin/env python3
"""ReportDesk — batch organize inspection reports (tkinter + SQLite)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.connection import default_db_path  # noqa: E402
from db.repository import Repository  # noqa: E402
from gui.main_window import MainWindow  # noqa: E402

PACKAGE_ROOT = Path(__file__).resolve().parent
CODE_BASE = PACKAGE_ROOT.parent
DEFAULT_CONTRACTS_XLSX = CODE_BASE / "合同.xlsx"


def _bootstrap_contracts(repo: Repository) -> None:
    """首次无合同数据时，尝试从默认 合同.xlsx 导入。"""
    try:
        if repo.count_project_contracts() > 0:
            return
    except Exception:
        return
    path = repo.get_setting("contracts_excel_path")
    candidates = [
        Path(path) if path else None,
        DEFAULT_CONTRACTS_XLSX,
        CODE_BASE.parent / "合同.xlsx",  # 兼容 limis-api/合同.xlsx 布局
        PACKAGE_ROOT / "data" / "合同.xlsx",
    ]
    for p in candidates:
        if p and p.is_file():
            try:
                repo.import_project_contracts_from_excel(p)
                if not repo.get_setting("contracts_excel_path"):
                    repo.set_setting("contracts_excel_path", str(p.resolve()))
                return
            except Exception:
                continue


def main() -> None:
    bootstrap = Repository.open()
    db = bootstrap.get_setting("db_path") or str(default_db_path())
    bootstrap.set_setting("db_path", db)
    repo = Repository.open(db)
    if not repo.get_setting("organize_folder_parent"):
        repo.set_setting("organize_folder_parent", "无")

    _bootstrap_contracts(repo)

    app = MainWindow(repo)
    app.mainloop()


if __name__ == "__main__":
    main()
