"""Settings dialog for LIMIS credentials and paths."""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.contract_paths import FOLDER_PARENT_NONE, VALID_FOLDER_PARENTS

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CODE_BASE = PACKAGE_ROOT.parent
SCAN_REPORT_ROOT = CODE_BASE / "ScanReport"
DEFAULT_OCR = SCAN_REPORT_ROOT / "tools" / "RapidOCR-json"
DEFAULT_CONTRACTS_XLSX = CODE_BASE / "合同.xlsx"

SETTING_KEYS = [
    "limis_base",
    "limis_user",
    "limis_password",
    "limis_auth_type",
    "rapidocr_dir",
    "scanreport_weights_dir",
    "output_root",
    "db_path",
    "organize_folder_parent",
    "contracts_excel_path",
]


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc, repo, on_saved) -> None:
        super().__init__(parent)
        self.repo = repo
        self.on_saved = on_saved
        self.title("ReportDesk 设置")
        self.resizable(True, True)
        self.grab_set()

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        self.vars: dict[str, tk.StringVar] = {}
        rows = [
            ("LIMIS 地址", "limis_base", False, False),
            ("LIMIS 用户名", "limis_user", False, False),
            ("LIMIS 密码", "limis_password", True, False),
            ("authType", "limis_auth_type", False, False),
            ("RapidOCR 目录", "rapidocr_dir", False, True),
            ("ScanReport 权重目录", "scanreport_weights_dir", False, True),
            ("输出根目录", "output_root", False, True),
            ("数据库路径", "db_path", False, True),
        ]
        defaults = {
            "limis_base": "http://10.1.228.22",
            "limis_auth_type": "1",
            "rapidocr_dir": str(DEFAULT_OCR) if DEFAULT_OCR.is_dir() else "",
            "scanreport_weights_dir": str(SCAN_REPORT_ROOT),
            "db_path": str(PACKAGE_ROOT / "data" / "reportdesk.db"),
            "organize_folder_parent": FOLDER_PARENT_NONE,
            "contracts_excel_path": str(DEFAULT_CONTRACTS_XLSX)
            if DEFAULT_CONTRACTS_XLSX.is_file()
            else "",
        }
        r = 0
        for label, key, secret, browse in rows:
            ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=2)
            v = tk.StringVar(value=self.repo.get_setting(key) or defaults.get(key, ""))
            self.vars[key] = v
            ent = ttk.Entry(frm, textvariable=v, width=48, show="*" if secret else "")
            ent.grid(row=r, column=1, sticky="ew", padx=4)
            if browse:
                ttk.Button(frm, text="浏览…", command=lambda k=key: self._browse(k)).grid(
                    row=r, column=2
                )
            r += 1

        ttk.Separator(frm, orient=tk.HORIZONTAL).grid(
            row=r, column=0, columnspan=3, sticky="ew", pady=8
        )
        r += 1

        ttk.Label(frm, text="工程目录上级").grid(row=r, column=0, sticky="w", pady=2)
        parent_val = self.repo.get_setting("organize_folder_parent") or FOLDER_PARENT_NONE
        self.vars["organize_folder_parent"] = tk.StringVar(value=parent_val)
        parent_cb = ttk.Combobox(
            frm,
            textvariable=self.vars["organize_folder_parent"],
            values=list(VALID_FOLDER_PARENTS),
            state="readonly",
            width=20,
        )
        parent_cb.grid(row=r, column=1, sticky="w", padx=4)
        ttk.Label(
            frm,
            text="须在合同表中精确匹配「项目名称」后才增加上级文件夹",
            foreground="gray",
        ).grid(row=r, column=2, sticky="w")
        r += 1

        ttk.Label(frm, text="合同表 Excel").grid(row=r, column=0, sticky="w", pady=2)
        v = tk.StringVar(
            value=self.repo.get_setting("contracts_excel_path") or defaults.get("contracts_excel_path", "")
        )
        self.vars["contracts_excel_path"] = v
        ttk.Entry(frm, textvariable=v, width=48).grid(row=r, column=1, sticky="ew", padx=4)
        ttk.Button(frm, text="浏览…", command=self._browse_contracts).grid(row=r, column=2)
        r += 1

        contract_btns = ttk.Frame(frm)
        contract_btns.grid(row=r, column=1, columnspan=2, sticky="w", pady=4)
        ttk.Button(contract_btns, text="导入合同表到数据库", command=self._import_contracts).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        self.contract_count_var = tk.StringVar(value=self._contract_count_text())
        ttk.Label(contract_btns, textvariable=self.contract_count_var).pack(side=tk.LEFT)
        r += 1

        frm.columnconfigure(1, weight=1)

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=r, column=0, columnspan=3, pady=(12, 0), sticky="e")
        ttk.Button(btn_row, text="测试内网登录", command=self._test_limis).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="保存", command=self._save).pack(side=tk.LEFT, padx=4)
        ttk.Button(btn_row, text="取消", command=self.destroy).pack(side=tk.LEFT)

    def _contract_count_text(self) -> str:
        try:
            n = self.repo.count_project_contracts()
        except Exception:
            n = 0
        return f"库内 {n} 条工程"

    def _browse(self, key: str) -> None:
        if key == "output_root" or key.endswith("_dir"):
            path = filedialog.askdirectory()
        else:
            path = filedialog.askopenfilename()
        if path:
            self.vars[key].set(path)

    def _browse_contracts(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")]
        )
        if path:
            self.vars["contracts_excel_path"].set(path)

    def _import_contracts(self) -> None:
        path = self.vars["contracts_excel_path"].get().strip()
        if not path:
            messagebox.showwarning("提示", "请先指定合同表 Excel 路径", parent=self)
            return
        try:
            n = self.repo.import_project_contracts_from_excel(path)
            self.contract_count_var.set(f"库内 {n} 条工程（已导入）")
            messagebox.showinfo("导入成功", f"已导入 {n} 条工程记录", parent=self)
        except Exception as e:
            messagebox.showerror("导入失败", str(e), parent=self)

    def _test_limis(self) -> None:
        try:
            sys.path.insert(0, str(CODE_BASE / "LimisQuery"))
            from limis_client import LimisClient, LimisConfig  # type: ignore

            cfg = LimisConfig(
                base_url=self.vars["limis_base"].get().strip(),
                username=self.vars["limis_user"].get().strip(),
                password=self.vars["limis_password"].get(),
                auth_type=self.vars["limis_auth_type"].get().strip() or "1",
            )
            client = LimisClient(cfg)
            data = client.login()
            messagebox.showinfo("登录", f"成功: state={data.get('state')}", parent=self)
        except Exception as e:
            messagebox.showerror("登录失败", str(e), parent=self)

    def _save(self) -> None:
        parent = self.vars["organize_folder_parent"].get().strip()
        if parent not in VALID_FOLDER_PARENTS:
            messagebox.showwarning(
                "提示",
                f"工程目录上级须为：{', '.join(VALID_FOLDER_PARENTS)}",
                parent=self,
            )
            return
        for key in SETTING_KEYS:
            self.repo.set_setting(key, self.vars[key].get().strip() or None)
        self.on_saved()
        self.destroy()
