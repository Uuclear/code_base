"""PaddleOCR-json CLI wrapper — https://github.com/hiroi-sora/PaddleOCR-json"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.ocr_json_util import parse_ocr_stdout, text_from_ocr_result

LABEL = "PaddleOCR"


def default_paddleocr_dir() -> Path | None:
    """Resolve PaddleOCR-json directory from env or ScanReport/tools."""
    env = os.environ.get("PADDLE_OCR_JSON") or os.environ.get("PADDLEOCR_JSON")
    if env:
        p = Path(env)
        if p.is_file():
            return p.parent
        if p.is_dir():
            return p
    candidate = Path(__file__).resolve().parents[1] / "tools" / "PaddleOCR-json"
    if candidate.is_dir():
        return candidate
    return None


def _find_exe(ocr_dir: Path) -> Path:
    for name in (
        "PaddleOCR-json.exe",
        "PaddleOCR_json.exe",
        "PaddleOCR-json",
        "PaddleOCR_json",
    ):
        p = ocr_dir / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"No PaddleOCR-json executable under {ocr_dir}")


def _find_python_api_dir(ocr_dir: Path) -> Path | None:
    for sub in ("api/python", "api/Python", "api"):
        for mod in ("PPOCR_api.py", "PaddleOCR_api.py"):
            api_dir = ocr_dir / sub
            if (api_dir / mod).is_file():
                return api_dir
    return None


def _run_via_python_api(image_path: Path, ocr_dir: Path) -> dict[str, Any]:
    api_dir = _find_python_api_dir(ocr_dir)
    if api_dir is None:
        raise FileNotFoundError("PPOCR_api.py not found under PaddleOCR-json")
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))
    from PPOCR_api import GetOcrApi  # type: ignore[import-not-found]

    exe = _find_exe(ocr_dir)
    ocr = GetOcrApi(str(exe))
    try:
        return ocr.run(str(image_path.resolve()))
    finally:
        for method in ("stop", "exit", "terminate"):
            fn = getattr(ocr, method, None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    pass
                break


def _run_via_cli(image_path: Path, ocr_dir: Path) -> dict[str, Any]:
    exe = _find_exe(ocr_dir)
    cmd = [str(exe), f"--image_path={image_path.resolve()}"]
    proc = subprocess.run(
        cmd,
        cwd=str(ocr_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(
            f"PaddleOCR-json exit {proc.returncode}: "
            f"{proc.stderr[:500] or proc.stdout[:500]}"
        )
    return parse_ocr_stdout(proc.stdout + "\n" + proc.stderr, label=LABEL)


def ocr_image_to_text(image_path: Path, ocr_dir: Path | None = None) -> str:
    """对图片运行 PaddleOCR-json，返回按行拼接的文本。"""
    base = ocr_dir or default_paddleocr_dir()
    if base is None:
        raise FileNotFoundError(
            "PaddleOCR-json not found. Set PADDLE_OCR_JSON to the extracted folder "
            "(see https://github.com/hiroi-sora/PaddleOCR-json)."
        )
    base = base.resolve()
    image_path = image_path.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    try:
        result = _run_via_python_api(image_path, base)
    except FileNotFoundError:
        result = _run_via_cli(image_path, base)

    return text_from_ocr_result(result, label=LABEL)
