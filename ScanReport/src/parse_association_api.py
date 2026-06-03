"""Parse SCETIA Vue anti-fake JSON APIs (rptverify + signboard)."""

from __future__ import annotations

from typing import Any

import requests

RPTVERIFY_API = "https://rptverify-service.scetia.com/api/rptAuthVerify/checkReport"
SIGNBOARD_API = "https://signboard-service.scetimis.com/api/user/checkReport"

RPTVERIFY_OK = 200
SIGNBOARD_OK = 200


def _json_headers(session: requests.Session) -> None:
    session.headers.setdefault("Accept", "application/json")
    session.headers.setdefault("Content-Type", "application/json")


def fetch_rptverify_json(
    report_no: str,
    check_code: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()
    _json_headers(sess)
    resp = sess.post(
        RPTVERIFY_API,
        json={"no": report_no, "checkCode": check_code},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_signboard_json(
    report_no: str,
    check_code: str,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    sess = session or requests.Session()
    _json_headers(sess)
    sess.headers.setdefault("Authorization", "")
    resp = sess.post(
        SIGNBOARD_API,
        json={"no": report_no, "checkCode": check_code},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _extract_report_url(payload: dict[str, Any], backend: str) -> str | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    url = data.get("reportUrl")
    return str(url).strip() if url else None


def is_rptverify_success(payload: dict[str, Any]) -> bool:
    return payload.get("resultCode") == RPTVERIFY_OK and bool(_extract_report_url(payload, "rptverify"))


def is_signboard_success(payload: dict[str, Any]) -> bool:
    if payload.get("code") == SIGNBOARD_OK:
        return bool(_extract_report_url(payload, "signboard"))
    if payload.get("resultCode") == SIGNBOARD_OK:
        return bool(_extract_report_url(payload, "signboard"))
    return False


def api_response_to_report(
    payload: dict[str, Any],
    *,
    backend: str,
    report_no: str,
    check_code: str,
) -> dict[str, Any]:
    """Map Vue checkReport JSON to the same top-level shape as HTML scraping."""
    pdf_url = _extract_report_url(payload, backend)
    project = {
        "report_no": report_no,
        "anti_fake_code": check_code,
    }
    if pdf_url:
        project["report_pdf_url"] = pdf_url

    return {
        "project": project,
        "samples": [],
        "report_pdf_url": pdf_url,
        "api_backend": backend,
        "raw": payload,
    }
