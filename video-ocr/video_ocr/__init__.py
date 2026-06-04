"""Video watermark OCR (PaddleOCR) + regex field extraction."""

from __future__ import annotations

from typing import Any

from video_ocr.models import WatermarkExtract, WatermarkPatterns
from video_ocr.regex_extract import extract_watermark_fields


def extract_watermark_from_video(*args: Any, **kwargs: Any) -> WatermarkExtract:
    """Lazy import so regex-only workflows do not require OpenCV/Paddle at import time."""
    from video_ocr.paddle_ocr_video import extract_watermark_from_video as _impl

    return _impl(*args, **kwargs)


__all__ = [
    "WatermarkExtract",
    "WatermarkPatterns",
    "extract_watermark_fields",
    "extract_watermark_from_video",
]
