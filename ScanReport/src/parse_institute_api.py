"""Parse jktac GetReportInfo JSON into normalized report dict."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

_DOTNET_DATE = re.compile(r"/Date\((\d+)\)/")


def parse_dotnet_date(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        m = _DOTNET_DATE.match(value.strip())
        if m:
            ts = int(m.group(1)) / 1000.0
            return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")
        if value and not value.startswith("/Date"):
            return value
    return None


def strip_html(html: str | None) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)


def api_response_to_report(data: dict[str, Any]) -> dict[str, Any]:
    """Map GetReportInfo fields to schema aligned with page labels."""
    testing_type = data.get("testingTypeName") or ""
    testing_date = parse_dotnet_date(data.get("testingDate"))
    if testing_type in ("见证", "见证取样") and data.get("samplingDate"):
        testing_date = parse_dotnet_date(data.get("samplingDate")) or testing_date

    project = {
        "report_no": data.get("testingReportNo") or data.get("testingReportCode"),
        "order_no": data.get("testingOrderNo"),
        "institute_name": data.get("testingInstituteName"),
        "unit_name": data.get("unitName"),
        "project_name": data.get("projectName"),
        "project_section": data.get("projectSection"),
        "report_date": parse_dotnet_date(data.get("reportDate")),
        "testing_date": testing_date,
        "testing_type": testing_type,
        "report_status": data.get("testingReportStatusName"),
    }

    sample = {
        "sample_no": data.get("sampleNo"),
        "sample_name": data.get("sampleName"),
        "manufacturer": data.get("productiveUnit"),
        "specification": data.get("specification"),
        "sample_level": data.get("sampleLevel"),
        "testing_basis": data.get("testingBasisItems"),
    }

    return {
        "project": {k: v for k, v in project.items() if v is not None and v != ""},
        "samples": [{k: v for k, v in sample.items() if v}],
        "testing_result": strip_html(data.get("testingResult")),
        "conclusion": data.get("testingConclusion") or data.get("conclusion"),
        "raw": data,
    }
