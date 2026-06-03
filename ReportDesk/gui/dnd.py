"""Windows 拖放：windnd 回调线程不得调用任何 Tk API（Python 3.12 GIL 崩溃）。"""

from __future__ import annotations

import queue
import sys
import tkinter as tk
from pathlib import Path
from typing import Callable

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp"}

# windnd 原生线程只往此队列塞路径字符串；主线程定时取出再处理
_pending_drop_paths: queue.Queue[list[str]] = queue.Queue()


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


def _decode_drop_item(f) -> str:
    if isinstance(f, bytes):
        s = f.decode("gbk", errors="replace")
    else:
        s = str(f)
    return s.strip().strip('"')


def start_drop_pump(root: tk.Misc, callback: Callable[[list[Path]], None]) -> None:
    """在主线程轮询拖放队列（须与 hook_dropfiles 成对调用）。"""
    if getattr(root, "_reportdesk_drop_pump", False):
        return
    root._reportdesk_drop_pump = True  # type: ignore[attr-defined]

    def _poll() -> None:
        try:
            while True:
                raw = _pending_drop_paths.get_nowait()
                if not raw:
                    continue
                paths = [Path(p) for p in raw]
                callback(collect_image_paths(paths))
        except queue.Empty:
            pass
        except Exception:
            pass
        root.after(30, _poll)

    root.after(30, _poll)


def hook_dropfiles(widget: tk.Misc, callback: Callable[[list[Path]], None]) -> bool:
    """注册拖放；callback 仅在 Tk 主线程执行。"""
    if sys.platform != "win32":
        return False
    try:
        import windnd  # type: ignore
    except ImportError:
        return False

    root = widget.winfo_toplevel()
    start_drop_pump(root, callback)

    def _on_drop(files: list) -> None:
        # 仅收集字符串入队，禁止在此线程调用 Tk / Path.glob / after
        try:
            raw = [_decode_drop_item(f) for f in files]
            raw = [p for p in raw if p]
            if raw:
                _pending_drop_paths.put(raw)
        except Exception:
            pass

    windnd.hook_dropfiles(widget, func=_on_drop)
    return True
