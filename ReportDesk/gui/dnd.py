"""Windows 拖放文件/文件夹（windnd 回调须派发到 Tk 主线程）。"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}


def collect_image_paths(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    seen: set[Path] = set()
    for p in paths:
        if p.is_dir():
            for pat in ("*.jpg", "*.jpeg", "*.png", "*.bmp", "*.JPG", "*.JPEG", "*.PNG"):
                for f in sorted(p.glob(pat)):
                    key = f.resolve()
                    if key not in seen:
                        seen.add(key)
                        out.append(f)
        elif p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES:
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out


def hook_dropfiles(widget: tk.Misc, callback: Callable[[list[Path]], None]) -> bool:
    """注册拖放；回调 guaranteed 在 Tk 主线程执行。"""
    if sys.platform != "win32":
        return False
    try:
        import windnd  # type: ignore
    except ImportError:
        return False

    root = widget.winfo_toplevel()

    def _on_drop(files: list) -> None:
        paths: list[Path] = []
        for f in files:
            if isinstance(f, bytes):
                s = f.decode("gbk", errors="replace")
            else:
                s = str(f)
            paths.append(Path(s.strip('"')))
        def _on_main_thread() -> None:
            # 路径收集与 Tk 均在主线程，避免与后台线程同时 import torch/scipy
            try:
                callback(collect_image_paths(paths))
            except Exception:
                pass

        # windnd 在本地线程回调，必须 after 到主线程再碰 Tk / 收集文件
        root.after(0, _on_main_thread)

    windnd.hook_dropfiles(widget, func=_on_drop)
    return True
