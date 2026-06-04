from __future__ import annotations

from collections import OrderedDict
from typing import Any

import cv2
import numpy as np

from video_ocr.models import WatermarkExtract, WatermarkPatterns
from video_ocr.regex_extract import extract_watermark_fields


def _lines_from_paddle_result(result: Any) -> list[str]:
    """Normalize PaddleOCR ``ocr()`` return value to text lines (roughly top-to-bottom)."""
    if result is None:
        return []
    block = result[0] if isinstance(result, (list, tuple)) and result else result
    if block is None:
        return []
    if not isinstance(block, list):
        return []

    scored: list[tuple[float, float, str]] = []
    for det in block:
        if det is None:
            continue
        if not isinstance(det, (list, tuple)) or len(det) < 2:
            continue
        box, rec = det[0], det[1]
        text = ""
        if isinstance(rec, (list, tuple)) and rec:
            text = str(rec[0])
        elif isinstance(rec, str):
            text = rec
        if not text.strip():
            continue
        y = x = 0.0
        if isinstance(box, (list, tuple)) and box:
            first = box[0]
            if isinstance(first, (list, tuple)) and len(first) >= 2:
                try:
                    ys = [float(p[1]) for p in box if isinstance(p, (list, tuple)) and len(p) > 1]
                    xs = [float(p[0]) for p in box if isinstance(p, (list, tuple)) and len(p) > 1]
                    if ys and xs:
                        y = sum(ys) / len(ys)
                        x = sum(xs) / len(xs)
                except (TypeError, ValueError):
                    y = x = 0.0
        scored.append((y, x, text.strip()))

    scored.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in scored]


def _unique_preserve(lines: list[str]) -> list[str]:
    out: "OrderedDict[str, None]" = OrderedDict()
    for ln in lines:
        if ln not in out:
            out[ln] = None
    return list(out.keys())


def extract_watermark_from_video(
    video_path: str,
    *,
    patterns: WatermarkPatterns | None = None,
    frame_interval: int = 15,
    max_frames: int | None = 40,
    region: tuple[int, int, int, int] | None = None,
    ocr_init_kwargs: dict[str, Any] | None = None,
) -> WatermarkExtract:
    """
    Sample frames from ``video_path``, run PaddleOCR, merge texts, then regex parse.

    :param frame_interval: read every Nth frame (>=1).
    :param max_frames: cap sampled frames; ``None`` for no cap (can be slow).
    :param region: optional ``(x, y, w, h)`` crop applied to each frame before OCR.
    :param ocr_init_kwargs: forwarded to ``PaddleOCR(...)`` (e.g. ``lang``, ``show_log``).
    """
    from paddleocr import PaddleOCR

    init = dict(use_angle_cls=True, lang="ch")
    if ocr_init_kwargs:
        init.update(ocr_init_kwargs)
    ocr = PaddleOCR(**init)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise FileNotFoundError(f"cannot open video: {video_path}")

    interval = max(1, int(frame_interval))
    collected: list[str] = []
    idx = 0
    sampled = 0

    try:
        while True:
            if max_frames is not None and sampled >= max_frames:
                break
            cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
            ok, frame = cap.read()
            if not ok or frame is None:
                break
            if region is not None:
                x, y, w, h = region
                x2 = min(frame.shape[1], x + max(w, 1))
                y2 = min(frame.shape[0], y + max(h, 1))
                frame = frame[y:y2, x:x2]
            if frame.size == 0:
                idx += interval
                continue

            # PaddleOCR expects uint8 BGR or RGB; VideoCapture is BGR.
            res = ocr.ocr(np.ascontiguousarray(frame), cls=True)
            collected.extend(_lines_from_paddle_result(res))
            sampled += 1
            idx += interval
    finally:
        cap.release()

    merged = _unique_preserve(collected)
    return extract_watermark_fields(merged, patterns)
