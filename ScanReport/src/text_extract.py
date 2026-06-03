"""Extract report identifiers from OCR plain text (no QR)."""

from __future__ import annotations

import re
from pathlib import Path

from src.qr_decode import (
    ASSOCIATION_HOSTS,
    DecodeResult,
    ReportType,
    _classify_qr_text,
    _extract_association_params,
)
from src.report_patterns import (
    LABEL_ANTI_FAKE,
    LABEL_REPORT_NO,
    LIMIS_INSTITUTE_REPORT_NO,
    excluded_from_anti_fake,
    find_limis_institute_report_no,
    is_valid_anti_fake,
)

URL_PATTERN = re.compile(r"https?://[^\s\]\)\"'<>]+", re.IGNORECASE)


def _labeled_report_no(text: str) -> str | None:
    m = LABEL_REPORT_NO.search(text)
    if not m:
        return None
    val = m.group(1)
    return val.upper() if val[0].isalpha() else val


def _labeled_anti_fake(text: str) -> str | None:
    m = LABEL_ANTI_FAKE.search(text)
    if not m:
        return None
    code = m.group(1)
    return code if is_valid_anti_fake(code, excluded_from_anti_fake(text)) else None


def normalize_ocr_text(text: str) -> str:
    """Collapse whitespace; unify full-width punctuation."""
    t = text.replace("｜", "|").replace("：", ":").replace("\u3000", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def _association_context(text: str) -> bool:
    lower = text.lower()
    if any(h in lower for h in ASSOCIATION_HOSTS):
        return True
    if "防伪" in text or "校验码" in text:
        return True
    if "建设工程检测行业协会" in text or "scetia" in lower:
        return True
    return False


def classify_from_ocr_text(text: str) -> tuple[ReportType, str | None, str | None]:
    """
    Classify OCR text.

    防伪码：仅「防伪校验码」标签后的 10 或 12 位数字（不用全文裸数字、不用 pipe 右侧）。
    二维码 ``编号|防伪`` 由 ``qr_decode`` 处理，不经过本函数。

    Priority:
    1. HTTP URL（院网 / 协会）
    2. 报告编号 + 防伪校验码（双标签）
    3. 协会：编号 + 标签防伪码（``_extract_association_params``）
    4. 仅内网/院网样式报告号 → LIMIS
    """
    normalized = normalize_ocr_text(text)
    if not normalized:
        return "unknown", None, None

    for url in URL_PATTERN.findall(normalized):
        rtype, rn, af = _classify_qr_text(url)
        if rtype == "institute":
            return "institute", None, None
        if rtype == "association":
            return "association", rn, af

    labeled_report = _labeled_report_no(normalized)
    labeled_fake = _labeled_anti_fake(normalized)

    if labeled_report and labeled_fake:
        return "association", labeled_report, labeled_fake

    report_no, anti_fake = _extract_association_params(
        normalized, allow_pipe_antifake=False
    )
    if report_no and anti_fake:
        return "association", report_no, anti_fake

    limis_no = find_limis_institute_report_no(normalized)
    if limis_no and not labeled_fake:
        if not _association_context(normalized):
            return "limis", limis_no, None

    if report_no and not anti_fake:
        if _association_context(normalized):
            return "unknown", report_no, None
        if limis_no:
            return "limis", limis_no, None
        m = LIMIS_INSTITUTE_REPORT_NO.search(normalized)
        if m:
            return "limis", m.group(1).upper(), None

    return "unknown", None, None


def decode_from_ocr_text(
    image_path: Path,
    ocr_text: str,
) -> DecodeResult | None:
    report_type, report_no, anti_fake = classify_from_ocr_text(ocr_text)
    if report_type == "unknown":
        return None

    preview = normalize_ocr_text(ocr_text)[:2000]
    qr_proxy = preview
    if report_no and anti_fake:
        qr_proxy = f"{report_no}|{anti_fake}"

    return DecodeResult(
        image=image_path.name,
        qr_texts=[qr_proxy],
        report_type=report_type,
        report_no=report_no,
        anti_fake_code=anti_fake,
        decode_source="ocr",
        ocr_text_preview=preview[:500],
    )
