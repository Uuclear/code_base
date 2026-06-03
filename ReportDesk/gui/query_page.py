"""报告库查询页：模糊搜索 + 列排序 + 底部文件预览 + 合同导入/CSV 导出。"""

from __future__ import annotations

import csv
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from core.date_format import format_report_date, parse_report_date_key
from db.repository import Repository
from gui.date_picker import DatePicker
from gui.image_preview import resolve_image_path, show_image_on_label

CODE_BASE = Path(__file__).resolve().parents[2]
DEFAULT_CONTRACTS_XLSX = CODE_BASE / "合同.xlsx"
EXPORT_LIMIT = 1_000_000

CHANNEL_LABEL = {
    "limis": "内网",
    "institute": "院网",
    "association": "协会",
}

COLUMNS = (
    "report_no",
    "order_no",
    "project_name",
    "manager",
    "handler",
    "sample_names",
    "report_date",
    "channel",
)
HEADINGS = {
    "report_no": "报告编号",
    "order_no": "委托编号",
    "project_name": "工程名称",
    "manager": "负责人",
    "handler": "经办人",
    "sample_names": "样品名称",
    "report_date": "报告日期",
    "channel": "渠道",
}
COL_WIDTH = {
    "report_no": 110,
    "order_no": 90,
    "project_name": 180,
    "manager": 72,
    "handler": 72,
    "sample_names": 100,
    "report_date": 88,
    "channel": 52,
}

CSV_HEADERS = [
    ("report_no", "报告编号"),
    ("order_no", "委托编号"),
    ("project_name", "工程名称"),
    ("manager", "负责人"),
    ("handler", "经办人"),
    ("sample_names", "样品名称"),
    ("report_date", "报告日期"),
    ("channel", "渠道"),
]


class QueryPage(ttk.Frame):
    def __init__(self, parent: tk.Misc, repo: Repository) -> None:
        super().__init__(parent, padding=6)
        self.repo = repo
        self._rows: list[dict] = []
        self._preview_photo = None
        self._sort_col: str | None = None
        self._sort_reverse = False
        self._file_paths: list[Path] = []

        self._build_ui()

    def _build_ui(self) -> None:
        form = ttk.LabelFrame(self, text="查询条件（支持模糊匹配）", padding=8)
        form.pack(fill=tk.X, pady=(0, 6))

        self.vars = {
            "order_no": tk.StringVar(),
            "report_no": tk.StringVar(),
            "project_name": tk.StringVar(),
            "sample_name": tk.StringVar(),
            "manager": tk.StringVar(),
            "handler": tk.StringVar(),
            "date_from": tk.StringVar(),
            "date_to": tk.StringVar(),
        }
        grid = ttk.Frame(form)
        grid.pack(fill=tk.X)

        text_fields = [
            ("order_no", "委托编号"),
            ("report_no", "报告编号"),
            ("project_name", "工程名称"),
            ("sample_name", "样品名称"),
            ("manager", "负责人"),
            ("handler", "经办人"),
        ]
        for i, (key, label) in enumerate(text_fields):
            r, c = divmod(i, 2)
            ttk.Label(grid, text=label, width=10).grid(row=r, column=c * 2, sticky="w", padx=2, pady=2)
            ttk.Entry(grid, textvariable=self.vars[key], width=24).grid(
                row=r, column=c * 2 + 1, sticky="ew", padx=2, pady=2
            )

        date_row = ttk.Frame(grid)
        date_row.grid(row=3, column=0, columnspan=4, sticky="w", pady=4)
        ttk.Label(date_row, text="报告日期起", width=10).pack(side=tk.LEFT)
        self._date_from_picker = DatePicker(date_row, textvariable=self.vars["date_from"])
        self._date_from_picker.pack(side=tk.LEFT, padx=(0, 16))
        ttk.Label(date_row, text="报告日期止", width=10).pack(side=tk.LEFT)
        self._date_to_picker = DatePicker(date_row, textvariable=self.vars["date_to"])
        self._date_to_picker.pack(side=tk.LEFT)

        for col in (1, 3):
            grid.columnconfigure(col, weight=1)

        btns = ttk.Frame(form)
        btns.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(btns, text="查询", command=self._search).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="清空条件", command=self._clear_form).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="导入合同表", command=self._import_contracts).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="导出 CSV", command=self._export_csv).pack(side=tk.LEFT, padx=2)
        self.result_count_var = tk.StringVar(value="")
        ttk.Label(btns, textvariable=self.result_count_var).pack(side=tk.RIGHT)

        mid = ttk.PanedWindow(self, orient=tk.VERTICAL)
        mid.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.LabelFrame(mid, text="查询结果（点击列头排序，点击行预览）", padding=4)
        mid.add(result_frame, weight=2)

        self.tree = ttk.Treeview(
            result_frame,
            columns=COLUMNS,
            show="headings",
            selectmode=tk.BROWSE,
            height=12,
        )
        for c in COLUMNS:
            self.tree.heading(
                c,
                text=HEADINGS[c],
                command=lambda col=c: self._on_heading_click(col),
            )
            self.tree.column(c, width=COL_WIDTH[c], anchor=tk.W)
        scroll_y = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        preview_frame = ttk.LabelFrame(mid, text="报告文件预览", padding=4)
        mid.add(preview_frame, weight=1)

        self.preview_label = tk.Label(
            preview_frame,
            text="选择上方记录以预览报告图片",
            anchor=tk.CENTER,
            bg="#f0f0f0",
        )
        self.preview_label.pack(fill=tk.BOTH, expand=True)

        self.file_list = tk.Listbox(preview_frame, height=2)
        self.file_list.pack(fill=tk.X, pady=(4, 0))
        self.file_list.bind("<<ListboxSelect>>", self._on_file_select)

    def _search_kwargs(self, *, limit: int = 300) -> dict:
        return {
            "order_no": self.vars["order_no"].get(),
            "report_no": self.vars["report_no"].get(),
            "project_name": self.vars["project_name"].get(),
            "sample_name": self.vars["sample_name"].get(),
            "manager": self.vars["manager"].get(),
            "handler": self.vars["handler"].get(),
            "date_from": self.vars["date_from"].get(),
            "date_to": self.vars["date_to"].get(),
            "limit": limit,
        }

    def _on_heading_click(self, col: str) -> None:
        if self._sort_col == col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False
        self._apply_sort()
        self._refresh_tree()

    def _heading_text(self, col: str) -> str:
        title = HEADINGS[col]
        if self._sort_col != col:
            return title
        arrow = " ↓" if self._sort_reverse else " ↑"
        return title + arrow

    def _update_headings(self) -> None:
        for c in COLUMNS:
            self.tree.heading(c, text=self._heading_text(c))

    def _sort_key(self, row: dict, col: str):
        if col == "report_date":
            return row.get("report_date_key") or parse_report_date_key(row.get("report_date")) or 0
        if col == "channel":
            raw = row.get("source_channel") or ""
            return CHANNEL_LABEL.get(raw, raw).lower()
        val = row.get(col) if col != "channel" else row.get("source_channel")
        return (str(val or "")).lower()

    def _apply_sort(self) -> None:
        if not self._sort_col or not self._rows:
            return
        col = self._sort_col
        self._rows.sort(key=lambda r: self._sort_key(r, col), reverse=self._sort_reverse)

    def _channel_display(self, row: dict) -> str:
        return CHANNEL_LABEL.get(row.get("source_channel") or "", row.get("source_channel") or "")

    def _row_values(self, row: dict) -> tuple[str, ...]:
        return (
            row.get("report_no") or "",
            row.get("order_no") or "",
            row.get("project_name") or "",
            row.get("manager") or "",
            row.get("handler") or "",
            row.get("sample_names") or "",
            row.get("report_date") or "",
            self._channel_display(row),
        )

    def _refresh_tree(self) -> None:
        self._update_headings()
        self.tree.delete(*self.tree.get_children())
        for i, row in enumerate(self._rows):
            self.tree.insert("", tk.END, iid=str(i), values=self._row_values(row))

    def _clear_form(self) -> None:
        for k, v in self.vars.items():
            v.set("")
        self._date_from_picker.clear()
        self._date_to_picker.clear()

    def _search(self) -> None:
        rows = self.repo.search_reports(**self._search_kwargs(limit=300))
        self._rows = rows
        if self._sort_col:
            self._apply_sort()
        else:
            self._sort_col = "report_date"
            self._sort_reverse = True
            self._apply_sort()
        self._refresh_tree()
        self.result_count_var.set(f"共 {len(rows)} 条" + ("（最多显示 300 条）" if len(rows) >= 300 else ""))
        self.preview_label.config(image="", text="选择上方记录以预览报告图片")
        self._preview_photo = None
        self.file_list.delete(0, tk.END)
        self._file_paths = []

    def _import_contracts(self) -> None:
        initial = str(DEFAULT_CONTRACTS_XLSX) if DEFAULT_CONTRACTS_XLSX.is_file() else ""
        path = filedialog.askopenfilename(
            title="选择合同表 Excel",
            initialfile=Path(initial).name if initial else "",
            initialdir=str(Path(initial).parent) if initial else str(CODE_BASE),
            filetypes=[("Excel", "*.xlsx *.xls"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            n = self.repo.import_project_contracts_from_excel(path)
            self.repo.set_setting("contracts_excel_path", str(Path(path).resolve()))
            messagebox.showinfo("导入成功", f"已导入 {n} 条工程记录（负责人/经办人）", parent=self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("导入失败", str(e), parent=self.winfo_toplevel())

    def _export_csv(self) -> None:
        rows = self.repo.search_reports(**self._search_kwargs(limit=EXPORT_LIMIT))
        if self._sort_col:
            rows.sort(key=lambda r: self._sort_key(r, self._sort_col), reverse=self._sort_reverse)
        if not rows:
            messagebox.showinfo("提示", "当前条件下无查询结果可导出", parent=self.winfo_toplevel())
            return
        path = filedialog.asksaveasfilename(
            title="导出查询结果为 CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All", "*.*")],
            initialfile="report_query.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([label for _, label in CSV_HEADERS])
                for row in rows:
                    out_row = []
                    for key, _ in CSV_HEADERS:
                        if key == "channel":
                            out_row.append(self._channel_display(row))
                        else:
                            out_row.append(row.get(key) or "")
                    writer.writerow(out_row)
            messagebox.showinfo(
                "导出成功",
                f"已导出 {len(rows)} 条到\n{path}",
                parent=self.winfo_toplevel(),
            )
        except OSError as e:
            messagebox.showerror("导出失败", str(e), parent=self.winfo_toplevel())

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        row = self._rows[int(sel[0])]
        report_no = row["report_no"]
        files = self.repo.list_report_files(report_no)
        self.file_list.delete(0, tk.END)
        self._file_paths = []
        for f in files:
            for key in ("stored_path", "original_path"):
                raw = f.get(key)
                if not raw:
                    continue
                resolved = resolve_image_path(raw)
                if resolved:
                    self._file_paths.append(resolved)
                    label = f"{f.get('file_index')}: {resolved.name}"
                    self.file_list.insert(tk.END, label)
                    break
        if self._file_paths:
            self.file_list.selection_set(0)
            self._show_path(self._file_paths[0])
            return
        prev = resolve_image_path(row.get("preview_path"))
        if prev:
            self._show_path(prev)
        else:
            self.preview_label.config(image="", text="无关联图片文件（路径不存在或未整理）")

    def _on_file_select(self, _evt=None) -> None:
        sel = self.file_list.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self._file_paths):
            self._show_path(self._file_paths[idx])

    def _show_path(self, path: Path) -> None:
        self._preview_photo = show_image_on_label(
            self.preview_label, path, max_size=(900, 360), empty_text="无法加载图片"
        )
