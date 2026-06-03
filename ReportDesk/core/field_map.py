"""UI 七项字段与三端爬取 JSON 的映射（见 LimisQuery/README.md）。"""

from __future__ import annotations

import re
from typing import Any

from core.date_format import format_report_date

# 界面主字段（可编辑）
UI_ENTRY_KEYS = (
    "qr_content",
    "order_no",
    "report_no",
    "project_name",
    "section",
    "sample_name",
    "report_date",
)

# 仅 OCR 回退时展示，置于右侧最下方（只读）
OCR_FIELD_KEY = "ocr_content"

UI_FIELD_KEYS = UI_ENTRY_KEYS + (OCR_FIELD_KEY,)

# 含内部字段（爬取协会时仍需 anti_fake_code）
FIELD_KEYS = UI_FIELD_KEYS + ("anti_fake_code",)

_OCR_MAX_LEN = 8000

_EMPTY_SECTION = frozenset({"", "-", "—", "－", "无", "暂无"})


def empty_fields() -> dict[str, str]:
    return {k: "" for k in FIELD_KEYS}


def _clean_section(value: str | None) -> str:
    if not value:
        return ""
    s = str(value).strip()
    return "" if s in _EMPTY_SECTION else s


def _limis_project_part(scrape: dict[str, Any]) -> str:
    detail = scrape.get("detail") or {}
    pages = detail.get("pages") or {}
    raw = pages.get("raw_delegation") or {}
    text = raw.get("text") or ""
    if text:
        m = re.search(r"工程部位\s*\n\s*([^\n]+)", text)
        if m:
            return m.group(1).strip()
    return ""


def _limis_sample_name(scrape: dict[str, Any]) -> str:
    detail = scrape.get("detail") or {}
    tasks = detail.get("tasks") or []
    if tasks:
        t0 = tasks[0]
        return str(t0.get("sampleName") or t0.get("taskName") or "").strip()
    pages = detail.get("pages") or {}
    raw = pages.get("raw_delegation") or {}
    fields = raw.get("fields") or {}
    for k, v in fields.items():
        if k == "1" and v and str(v) != "样品名称":
            return str(v).strip()
    return ""


def _limis_report_date(scrape: dict[str, Any]) -> str:
    detail = scrape.get("detail") or {}
    report = detail.get("report") or {}
    hist = report.get("audit_history") or []
    if hist:
        last = hist[-1].get("createTime")
        if last:
            return str(last).strip()
    onclick = report.get("onclick") or ""
    m = re.search(r"/Output/(\d{4})/(\d{2})/", onclick)
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    row = scrape.get("integrated_list_row") or {}
    return str(row.get("testingOrderTime") or row.get("samplingDate") or "").strip()


def fields_from_decode(
    *,
    qr_content: str = "",
    report_type: str | None = None,
    report_no: str | None = None,
    anti_fake_code: str | None = None,
    ocr_preview: str | None = None,
    decode_method: str | None = None,
) -> dict[str, str]:
    f = empty_fields()
    f["report_no"] = (report_no or "").strip()
    f["anti_fake_code"] = (anti_fake_code or "").strip()
    if decode_method == "ocr":
        f["qr_content"] = ""
        preview = (ocr_preview or "").strip()
        if preview:
            f["ocr_content"] = preview[:_OCR_MAX_LEN]
    else:
        f["qr_content"] = (qr_content or "").strip()
        preview = (ocr_preview or "").strip()
        if preview:
            f["ocr_content"] = preview[:_OCR_MAX_LEN]
    return f


def fields_from_scrape(scrape: dict[str, Any] | None, report_type: str | None) -> dict[str, str]:
    """从爬取结果填充七项 + 防伪码；三端路径按 README 对照表。"""
    f = empty_fields()
    if not scrape:
        return f

    q = scrape.get("query") or {}
    proj = scrape.get("project") or {}
    samples = scrape.get("samples") or []

    ident = scrape.get("identification") or {}
    decode_method = str(ident.get("method") or "").lower()
    ocr_preview = ident.get("ocr_text_preview") or ""

    if decode_method == "ocr":
        raw = str(ocr_preview or scrape.get("qr_content") or "").strip()
        if raw:
            f["ocr_content"] = raw[:_OCR_MAX_LEN]
        f["qr_content"] = ""
    else:
        f["qr_content"] = str(
            scrape.get("qr_content") or q.get("qr_content") or ""
        ).strip()
        if ocr_preview and decode_method != "ocr":
            f["ocr_content"] = str(ocr_preview)[:_OCR_MAX_LEN]

    rt = report_type or scrape.get("report_type")

    if rt == "association":
        if not _association_has_data(proj, samples):
            return f
        f["order_no"] = str(proj.get("consign_no") or q.get("consign_no") or "")
        f["report_no"] = str(proj.get("report_no") or q.get("report_no") or "")
        f["anti_fake_code"] = str(proj.get("anti_fake_code") or q.get("anti_fake_code") or "")
        f["project_name"] = str(proj.get("project_name") or "")
        f["section"] = _clean_section(proj.get("project_section"))
        f["report_date"] = format_report_date(proj.get("report_date"))
        if samples:
            f["sample_name"] = str(samples[0].get("sample_name") or "")
        elif proj.get("testing_type"):
            f["sample_name"] = str(proj.get("testing_type"))

    elif rt == "institute":
        f["order_no"] = str(proj.get("order_no") or q.get("order_no") or "")
        f["report_no"] = str(proj.get("report_no") or q.get("r_no") or "")
        f["project_name"] = str(proj.get("project_name") or "")
        f["section"] = ""  # 院网无「标段」；部位在 project_section，不填入标段列
        f["report_date"] = format_report_date(proj.get("report_date"))
        if samples:
            f["sample_name"] = str(samples[0].get("sample_name") or "")
        else:
            f["sample_name"] = str(proj.get("sample_name") or "")

    elif rt == "limis":
        row = scrape.get("integrated_list_row") or {}
        match = scrape.get("match") or {}
        f["report_no"] = str(match.get("testingReportNo") or q.get("report_no") or "")
        f["order_no"] = str(
            match.get("testingOrderNo") or row.get("testingOrderNo") or ""
        )
        f["project_name"] = str(row.get("projectName") or "")
        f["section"] = ""  # 内网列表无标段；工程部位见 normalize.project_part
        f["sample_name"] = _limis_sample_name(scrape)
        f["report_date"] = format_report_date(_limis_report_date(scrape))

    return f


def _association_has_data(proj: dict[str, Any], samples: list[Any]) -> bool:
    if samples:
        return True
    return bool(
        (proj.get("project_name") or "").strip()
        or (proj.get("report_no") or "").strip()
    )


def merge_field_dict(base: dict[str, str], override: dict[str, str]) -> dict[str, str]:
    out = dict(base)
    for k, v in override.items():
        if k in out and v is not None and str(v).strip():
            out[k] = str(v).strip()
    return out


def ui_fields_dict(full: dict[str, str]) -> dict[str, str]:
    return {k: full.get(k, "") for k in UI_FIELD_KEYS}
