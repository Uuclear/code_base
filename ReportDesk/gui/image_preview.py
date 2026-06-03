"""在 tkinter Label 上显示图片预览（须用 tk.Label，ttk.Label 不支持 image）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None  # type: ignore
    ImageTk = None  # type: ignore


def resolve_image_path(path: Path | str | None) -> Path | None:
    """解析并确认图片文件存在。"""
    if not path:
        return None
    p = Path(path)
    candidates = [p, p.resolve()]
    if not p.is_absolute():
        candidates.append(Path.cwd() / p)
    seen: set[Path] = set()
    for c in candidates:
        try:
            key = c.resolve()
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        if key.is_file():
            return key
    return None


def show_image_on_label(
    label,
    path: Path | str | None,
    *,
    max_size: tuple[int, int] = (520, 680),
    empty_text: str = "无预览",
) -> Any:
    """加载图片到 Label，返回需保持引用的 PhotoImage。"""
    resolved = resolve_image_path(path)
    if resolved is None:
        hint = str(path) if path else empty_text
        if path and not Path(path).is_file():
            hint = f"文件不存在:\n{path}"
        label.config(image="", text=hint)
        return None
    if Image is None or ImageTk is None:
        label.config(image="", text=str(resolved))
        return None
    try:
        img = Image.open(resolved)
        img.thumbnail(max_size)
        photo = ImageTk.PhotoImage(img)
        label.config(image=photo, text="")
        return photo
    except Exception as e:
        label.config(image="", text=f"无法预览: {e}\n{resolved}")
        return None
