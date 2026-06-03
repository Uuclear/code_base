"""QR code detection and decoding for report images."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import cv2
from qreader import QReader

from src.report_patterns import (
    ASSOCIATION_REPORT_ALNUM,
    PIPE_ASSOCIATION_PATTERN,
    find_anti_fake_code,
    find_association_report_no,
)

ReportType = Literal["association", "institute", "limis", "unknown"]

ASSOCIATION_HOSTS = (
    "scetia.com",
    "scetimis.com",
    "rptverify.scetia.com",
    "signboard.scetimis.com",
)


@dataclass
class DecodeResult:
    image: str
    qr_texts: list[str]
    report_type: ReportType
    report_no: str | None = None
    anti_fake_code: str | None = None
    decode_source: Literal["qr", "ocr"] = "qr"
    ocr_text_preview: str | None = None


_qreader: QReader | None = None


def get_qreader(weights_folder: Path | None = None) -> QReader:
    global _qreader
    if _qreader is None:
        kwargs: dict = {"model_size": "s", "reencode_to": "cp65001"}
        if weights_folder and weights_folder.is_dir():
            kwargs["weights_folder"] = str(weights_folder)
        _qreader = QReader(**kwargs)
    return _qreader


def _classify_qr_text(text: str) -> tuple[ReportType, str | None, str | None]:
    lower = text.lower()
    if any(host in lower for host in ASSOCIATION_HOSTS):
        return "association", *_extract_association_params(text)
    if text.strip().lower().startswith(("http://", "https://")):
        if any(host in lower for host in ASSOCIATION_HOSTS):
            return "association", *_extract_params_from_url(text)
        return "institute", None, None
    report_no, code = _extract_association_params(text)
    if report_no or code:
        return "association", report_no, code
    return "unknown", None, None


def _extract_params_from_url(url: str) -> tuple[str | None, str | None]:
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    report_no = (
        (qs.get("rqstConsignID") or qs.get("reportNo") or qs.get("ReportNo") or [None])[0]
    )
    code = (
        (qs.get("rqstIdentifyingCode") or qs.get("code") or qs.get("CheckCode") or [None])[0]
    )
    if report_no or code:
        return report_no, code
    return _extract_association_params(url)


def _parse_pipe_qr(text: str) -> tuple[str | None, str | None]:
    m = PIPE_ASSOCIATION_PATTERN.search(text)
    if m:
        rn = m.group(1)
        code = m.group(2)
        if rn[0].isalpha():
            rn = rn.upper()
        return rn, code
    if "|" in text:
        parts = text.strip().split("|", 1)
        if len(parts) == 2:
            rn, code = parts[0].strip(), parts[1].strip()
            if rn and code.isdigit() and len(code) in (10, 12):
                if ASSOCIATION_REPORT_ALNUM.fullmatch(rn) or re.fullmatch(r"\d{4,10}", rn):
                    return (rn.upper() if rn[0].isalpha() else rn), code
    return None, None


def _extract_association_params(
    text: str,
    *,
    allow_pipe_antifake: bool = True,
) -> tuple[str | None, str | None]:
    """QR/URL 可用 ``编号|防伪``；OCR 须 ``allow_pipe_antifake=False``。"""
    if allow_pipe_antifake:
        report_no, code = _parse_pipe_qr(text)
        if report_no and code:
            return report_no, code

    report_no = find_association_report_no(text, allow_pipe=allow_pipe_antifake)
    code = find_anti_fake_code(text)
    return report_no, code


def _extract_params_from_text(text: str) -> tuple[str | None, str | None]:
    """Backward-compatible alias for association extraction."""
    return _extract_association_params(text)


def classify_from_qr_texts(qr_texts: list[str]) -> tuple[ReportType, str | None, str | None]:
    report_type: ReportType = "unknown"
    report_no: str | None = None
    anti_fake: str | None = None
    for text in qr_texts:
        if not text:
            continue
        t, rn, af = _classify_qr_text(text)
        if t == "institute":
            return "institute", None, None
        if t == "association":
            report_type = "association"
            report_no = report_no or rn
            anti_fake = anti_fake or af
        elif t == "unknown" and report_type == "unknown":
            report_type = "unknown"
    if report_type == "unknown" and any(
        t.strip().lower().startswith(("http://", "https://")) for t in qr_texts if t
    ):
        return "institute", None, None
    return report_type, report_no, anti_fake


def decode_image(
    image_path: Path,
    weights_folder: Path | None = None,
) -> DecodeResult | None:
    """Decode QR from image. Returns None if no QR found."""
    img = cv2.imread(str(image_path))
    if img is None:
        raise ValueError(f"Cannot read image: {image_path}")

    reader = get_qreader(weights_folder)
    decoded = reader.detect_and_decode(image=img, is_bgr=True)

    qr_texts: list[str] = []
    if decoded:
        for item in decoded:
            if item is None:
                continue
            if isinstance(item, (list, tuple)):
                qr_texts.extend(str(x) for x in item if x)
            else:
                qr_texts.append(str(item))

    qr_texts = [t.strip() for t in qr_texts if t and str(t).strip()]
    if not qr_texts:
        return None

    report_type, report_no, anti_fake = classify_from_qr_texts(qr_texts)
    return DecodeResult(
        image=image_path.name,
        qr_texts=qr_texts,
        report_type=report_type,
        report_no=report_no,
        anti_fake_code=anti_fake,
    )
