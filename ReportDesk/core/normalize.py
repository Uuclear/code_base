"""Map ScanReport scrape JSON into DB bundle (reports + child tables)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from core.date_format import format_report_date


_PROJECT_PART_RE = re.compile(r"工程部位[：:\s]*([^\n\r]+)")


def normalize_report_no(value: str | None) -> str | None:
    if not value or not str(value).strip():
        return None
    return str(value).strip().upper()


def section_folder_for_association(section: str | None) -> str | None:
    """协会页「标段」；无有效值时返回 None（文件不落 _无标段 子目录）。"""
    if not section or str(section).strip() in ("", "-", "—", "－"):
        return None
    return str(section).strip()


def _extract_limis_project_part(data: dict[str, Any]) -> str | None:
    detail = data.get("detail") or {}
    pages = detail.get("pages") or {}
    raw = pages.get("raw_delegation") or {}
    text = raw.get("text") or ""
    if not text:
        return None
    m = _PROJECT_PART_RE.search(text)
    return m.group(1).strip() if m else None


def _first_sample(data: dict[str, Any]) -> dict[str, Any]:
    samples = data.get("samples") or []
    return samples[0] if samples else {}


def _conclusion_summary(data: dict[str, Any], report_type: str) -> str | None:
    if report_type == "association":
        proj = data.get("project") or {}
        conc = proj.get("report_conclusions") or []
        if conc:
            return conc[0].get("conclusion")
        s = _first_sample(data)
        return s.get("exam_result")
    if report_type == "institute":
        return data.get("testing_result") or data.get("conclusion")
    return None


def normalize_from_scrape(
    scrape: dict[str, Any] | None,
    *,
    report_no: str,
    source_channel: str,
    decode_method: str,
    source_image: str,
) -> dict[str, Any]:
    """Full bundle after successful scrape."""
    rn = normalize_report_no(report_no) or report_no
    now = datetime.now(timezone.utc).isoformat()
    report: dict[str, Any] = {
        "report_no": rn,
        "source_channel": source_channel,
        "decode_method": decode_method,
        "scrape_status": "ok",
        "scrape_json": json.dumps(scrape, ensure_ascii=False) if scrape else None,
        "scraped_at": scrape.get("scraped_at") if scrape else now,
    }

    samples: list[dict[str, Any]] = []
    tasks: list[dict[str, Any]] = []
    audit_history: list[dict[str, Any]] = []
    integrated: dict[str, Any] | None = None

    if source_channel == "limis" and scrape:
        match = scrape.get("match") or {}
        row = scrape.get("integrated_list_row") or {}
        report.update(
            {
                "order_no": match.get("testingOrderNo"),
                "testing_report_id": str(match.get("testingReportId") or "") or None,
                "testing_order_id": match.get("testingOrderId"),
                "project_name": row.get("projectName"),
                "project_part": _extract_limis_project_part(scrape),
                "section_folder": None,
                "unit_name": row.get("testingOrderUnitName"),
                "unit_code": row.get("testingOrderUnitCode"),
                "institute_name": row.get("testingInstituteName"),
                "contract_no": row.get("testingOrderContractNo"),
                "total_fee": row.get("totalFee"),
                "order_time": row.get("testingOrderTime"),
                "sampling_date": row.get("samplingDate"),
                "report_status": match.get("report_status"),
                "testing_type_code": row.get("testingTypeCode"),
                "testing_type_name": row.get("testingOrderTypeDesp"),
                "change_status": row.get("changeStatus"),
            }
        )
        integrated = row
        detail = scrape.get("detail") or {}
        for t in detail.get("tasks") or []:
            tasks.append(
                {
                    "task_id": t.get("taskId"),
                    "sample_id": t.get("sampleId"),
                    "task_name": t.get("taskName"),
                    "sample_no": t.get("sampleNo"),
                    "sample_name": t.get("sampleName"),
                    "task_status_name": t.get("taskStatusName"),
                    "dept_name": t.get("deptName"),
                    "editor": t.get("editor"),
                    "raw_json": t,
                }
            )
        rep = detail.get("report") or {}
        for a in rep.get("audit_history") or []:
            audit_history.append(
                {
                    "audit_user_name": a.get("auditUserName"),
                    "audit_result": a.get("auditResult"),
                    "create_time": a.get("createTime"),
                    "raw_json": a,
                }
            )

    elif source_channel == "institute" and scrape:
        proj = scrape.get("project") or {}
        query = scrape.get("query") or {}
        report.update(
            {
                "order_no": proj.get("order_no"),
                "institute_r_id_raw": query.get("r_id_raw"),
                "testing_report_id": str(query.get("r_id_decoded") or "") or None,
                "project_name": proj.get("project_name"),
                "project_part": proj.get("project_section"),
                "section_folder": None,
                "unit_name": proj.get("unit_name"),
                "institute_name": proj.get("institute_name"),
                "report_date": format_report_date(proj.get("report_date")),
                "testing_date": proj.get("testing_date"),
                "testing_type_name": proj.get("testing_type"),
                "report_status": proj.get("report_status"),
                "testing_result": scrape.get("testing_result"),
            }
        )
        for i, s in enumerate(scrape.get("samples") or []):
            samples.append(
                {
                    "sample_no": s.get("sample_no"),
                    "sample_name": s.get("sample_name"),
                    "specification": s.get("specification"),
                    "grade": s.get("sample_level") or s.get("grade"),
                    "manufacturer": s.get("manufacturer"),
                    "testing_date": proj.get("testing_date"),
                    "extra_json": s,
                }
            )

    elif source_channel == "association" and scrape:
        proj = scrape.get("project") or {}
        report.update(
            {
                "order_no": proj.get("consign_no"),
                "anti_fake_code": proj.get("anti_fake_code"),
                "project_name": proj.get("project_name"),
                "project_address": proj.get("project_address"),
                "project_part": _first_sample(scrape).get("project_part"),
                "section_folder": section_folder_for_association(proj.get("project_section")),
                "project_section_extra": proj.get("project_section_extra"),
                "project_serial_no": proj.get("project_serial_no"),
                "unit_name": proj.get("unit_name"),
                "institute_name": proj.get("institute_name"),
                "institute_address": proj.get("institute_address"),
                "institute_phone": proj.get("institute_phone"),
                "institute_postcode": proj.get("institute_postcode"),
                "construction_unit": proj.get("construction_unit"),
                "witness_unit": proj.get("witness_unit"),
                "sampler": proj.get("sampler"),
                "witness": proj.get("witness"),
                "consign_date": proj.get("consign_date"),
                "report_date": format_report_date(proj.get("report_date")),
                "consign_type": proj.get("consign_type"),
            }
        )
        report["conclusion_summary"] = _conclusion_summary(scrape, "association")
        for i, s in enumerate(scrape.get("samples") or []):
            samples.append(
                {
                    "sample_no": s.get("sample_no"),
                    "sample_name": s.get("sample_name"),
                    "specification": s.get("specification"),
                    "grade": s.get("grade"),
                    "project_part": s.get("project_part"),
                    "exam_result": s.get("exam_result"),
                    "testing_date": s.get("testing_date"),
                    "manufacturer": s.get("manufacturer"),
                    "delegate_quantity": s.get("delegate_quantity"),
                    "molding_date": s.get("molding_date"),
                    "age_time": s.get("age_time"),
                    "extra_json": s,
                }
            )

    report["conclusion_summary"] = report.get("conclusion_summary") or _conclusion_summary(
        scrape or {}, source_channel
    )
    return {
        "report": report,
        "samples": samples,
        "tasks": tasks,
        "audit_history": audit_history,
        "integrated_list_row": integrated,
    }


def normalize_partial(
    report_no: str,
    source_channel: str,
    decode_method: str,
    *,
    error: str | None = None,
) -> dict[str, Any]:
    """Minimal row when scrape failed but report_no is known."""
    rn = normalize_report_no(report_no) or report_no
    return {
        "report": {
            "report_no": rn,
            "source_channel": source_channel,
            "decode_method": decode_method,
            "scrape_status": "partial",
            "section_folder": None,
            "project_name": None,
            "scrape_json": json.dumps({"error": error}, ensure_ascii=False) if error else None,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        },
        "samples": [],
        "tasks": [],
        "audit_history": [],
        "integrated_list_row": None,
    }
