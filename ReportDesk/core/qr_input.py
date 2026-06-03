"""扫码枪 / 人工输入的二维码文本解析。"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

CODE_BASE = Path(__file__).resolve().parents[2]
SCAN_REPORT_ROOT = CODE_BASE / "ScanReport"


def _ensure_scanreport() -> None:
    root = str(SCAN_REPORT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def parse_qr_text(text: str) -> dict[str, str]:
    _ensure_scanreport()
    from src.qr_decode import (  # type: ignore
        DecodeResult,
        classify_from_qr_texts,
        _extract_association_params,
    )

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        lines = [text.strip()]
    report_type, report_no, anti_fake = classify_from_qr_texts(lines)
    if not report_no or not anti_fake:
        rn, af = _extract_association_params(text, allow_pipe_antifake=True)
        report_no = report_no or rn or ""
        anti_fake = anti_fake or af or ""
    return {
        "report_no": (report_no or "").strip(),
        "anti_fake_code": (anti_fake or "").strip(),
        "report_type": report_type or "",
    }


def build_decode_from_fields(image_name: str, fields: dict[str, str]) -> Any:
    _ensure_scanreport()
    from src.qr_decode import DecodeResult  # type: ignore

    qr = fields.get("qr_content") or ""
    lines = [ln for ln in qr.splitlines() if ln.strip()] or ([qr] if qr else [])
    report_type = fields.get("report_type") or "association"
    if fields.get("anti_fake_code"):
        report_type = "association"
    return DecodeResult(
        image=image_name,
        qr_texts=lines,
        report_type=report_type,  # type: ignore[arg-type]
        report_no=fields.get("report_no") or None,
        anti_fake_code=fields.get("anti_fake_code") or None,
        decode_source="manual",
    )
