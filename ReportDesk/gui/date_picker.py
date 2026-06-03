"""日期选择控件（优先 tkcalendar，否则文本框）。"""

from __future__ import annotations

import tkinter as tk
from datetime import date
from tkinter import ttk


class DatePicker(ttk.Frame):
    """返回 YYYY-MM-DD 字符串；绑定 StringVar。"""

    def __init__(self, parent: tk.Misc, textvariable: tk.StringVar | None = None, **kw) -> None:
        super().__init__(parent, **kw)
        self.var = textvariable or tk.StringVar()
        self._use_calendar = False
        try:
            from tkcalendar import DateEntry  # type: ignore

            self._entry = DateEntry(
                self,
                width=12,
                date_pattern="yyyy-mm-dd",
                textvariable=self.var,
            )
            self._entry.pack(side=tk.LEFT)
            self._use_calendar = True
            ttk.Button(self, text="清空", width=4, command=self.clear).pack(side=tk.LEFT, padx=2)
        except ImportError:
            ttk.Entry(self, textvariable=self.var, width=12).pack(side=tk.LEFT)
            ttk.Button(self, text="今天", width=4, command=self._set_today).pack(side=tk.LEFT, padx=2)
            ttk.Button(self, text="清空", width=4, command=self.clear).pack(side=tk.LEFT)

    def _set_today(self) -> None:
        self.var.set(date.today().strftime("%Y-%m-%d"))

    def clear(self) -> None:
        self.var.set("")

    def get(self) -> str:
        return self.var.get().strip()
