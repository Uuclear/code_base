"""统一 OCR 回退：RapidOCR-json（偏 Windows）与 PaddleOCR-json（Windows/Linux）。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Literal

from src import paddleocr_client, rapidocr_client

OcrEngine = Literal["auto", "rapidocr", "paddleocr"]


def _norm_engine(engine: str | None) -> OcrEngine:
    v = (engine or "auto").strip().lower()
    if v in ("rapidocr", "rapid", "rapidocr-json"):
        return "rapidocr"
    if v in ("paddleocr", "paddle", "paddleocr-json"):
        return "paddleocr"
    return "auto"


def any_ocr_configured(
    rapidocr_dir: Path | None = None,
    paddleocr_dir: Path | None = None,
) -> bool:
    if rapidocr_dir and Path(rapidocr_dir).is_dir():
        return True
    if paddleocr_dir and Path(paddleocr_dir).is_dir():
        return True
    if rapidocr_client.default_rapidocr_dir() is not None:
        return True
    if paddleocr_client.default_paddleocr_dir() is not None:
        return True
    return False


def ocr_image_to_text(
    image_path: Path,
    *,
    engine: str | None = "auto",
    rapidocr_dir: Path | None = None,
    paddleocr_dir: Path | None = None,
) -> str:
    """
    无 QR 时的 OCR 回退。

    engine:
      - rapidocr: 仅 RapidOCR-json
      - paddleocr: 仅 PaddleOCR-json
      - auto: Windows 优先 RapidOCR，否则 PaddleOCR；非 Windows 用 PaddleOCR
    """
    eng = _norm_engine(engine)

    if eng == "rapidocr":
        return rapidocr_client.ocr_image_to_text(image_path, rapidocr_dir)

    if eng == "paddleocr":
        return paddleocr_client.ocr_image_to_text(image_path, paddleocr_dir)

    # auto
    if sys.platform == "win32":
        try:
            return rapidocr_client.ocr_image_to_text(image_path, rapidocr_dir)
        except FileNotFoundError:
            pass
    return paddleocr_client.ocr_image_to_text(image_path, paddleocr_dir)
