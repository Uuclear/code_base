"""ReportDesk 主窗口：整理 + 查询 标签页。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from db.repository import Repository
from gui.organize_tab import OrganizeTab
from gui.query_page import QueryPage


class MainWindow(tk.Tk):
    def __init__(self, repo: Repository) -> None:
        super().__init__()
        self.repo = repo
        self.title("ReportDesk — 报告整理")
        self.geometry("1280x760")
        self.minsize(1000, 620)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        self.organize_tab = OrganizeTab(self.notebook, repo)
        self.query_tab = QueryPage(self.notebook, repo)

        self.notebook.add(self.organize_tab, text="整理")
        self.notebook.add(self.query_tab, text="查询")
