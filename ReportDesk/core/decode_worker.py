"""子进程 QR/OCR 解码（与 Tk 主进程隔离，避免界面假死与 GIL 冲突）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, cast

from .decoded_snapshot import DecodedSnapshot, ReportType
from .pipeline import DecodeOutcome


def _as_report_type(value: str | None) -> ReportType:
    if value in ("association", "institute", "limis", "unknown"):
        return cast(ReportType, value)
    return "unknown"


def _as_decode_source(value: str | None) -> Literal["qr", "ocr", "manual"]:
    if value in ("qr", "ocr", "manual"):
        return cast(Literal["qr", "ocr", "manual"], value)
    return "qr"


def decode_path_in_subprocess(path_str: str) -> dict[str, Any]:
    """在 ProcessPool 子进程中执行 decode_image，返回可 pickle 的 dict。"""
    from .mp_worker import _pipeline

    if _pipeline is None:
        raise RuntimeError("decode pool not initialized")

    outcome = _pipeline.decode_image(Path(path_str))
    decoded = outcome.decoded
    qr_texts: list[str] = []
    if decoded is not None:
        qr_texts = [t for t in (getattr(decoded, "qr_texts", None) or []) if t]

    return {
        "status": outcome.status,
        "source_image": outcome.source_image,
        "report_type": outcome.report_type,
        "report_no": outcome.report_no,
        "anti_fake_code": outcome.anti_fake_code,
        "decode_method": outcome.decode_method,
        "qr_text": outcome.qr_text,
        "ocr_preview": outcome.ocr_preview,
        "error": outcome.error,
        "qr_texts": qr_texts,
        "has_decoded": decoded is not None,
    }


def dict_to_decode_outcome(data: dict[str, Any]) -> DecodeOutcome:
    decoded: DecodedSnapshot | None = None
    if data.get("has_decoded"):
        decoded = DecodedSnapshot(
            image=data.get("source_image") or "",
            qr_texts=list(data.get("qr_texts") or []),
            report_type=_as_report_type(data.get("report_type")),
            report_no=data.get("report_no"),
            anti_fake_code=data.get("anti_fake_code"),
            decode_source=_as_decode_source(data.get("decode_method")),
            ocr_text_preview=data.get("ocr_preview"),
        )
    return DecodeOutcome(
        data.get("status") or "failed",
        data.get("source_image") or "",
        decoded=decoded,
        report_type=data.get("report_type"),
        report_no=data.get("report_no"),
        anti_fake_code=data.get("anti_fake_code"),
        decode_method=data.get("decode_method"),
        qr_text=data.get("qr_text") or "",
        ocr_preview=data.get("ocr_preview"),
        error=data.get("error"),
    )
