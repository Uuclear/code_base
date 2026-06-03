"""Scrape SCETIA association reports via anti-fake query endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

import requests

from src.parse_association_api import (
    RPTVERIFY_API,
    SIGNBOARD_API,
    api_response_to_report,
    fetch_rptverify_json,
    fetch_signboard_json,
    is_rptverify_success,
    is_signboard_success,
)
from src.parse_html import parse_association_html
from src.qr_decode import DecodeResult

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT_POST = 60
TIMEOUT_GET = 30

AssociationBackend = Literal[
    "material_html",
    "scetimis_html",
    "rptverify_json",
    "signboard_json",
]


@dataclass
class AssociationQuery:
    report_no: str
    anti_fake_code: str
    endpoint: str
    method: str
    backend: AssociationBackend


def resolve_association_backend(anti_fake_code: str) -> AssociationBackend:
    """Route by anti-fake code length/prefix (scetia front-end rules)."""
    code = anti_fake_code.strip()
    length = len(code)
    if length == 12 and code.startswith("3001"):
        return "signboard_json"
    if length == 11 or (length == 12 and code.startswith("0")):
        return "rptverify_json"
    if length == 10:
        return "scetimis_html"
    return "material_html"


def resolve_endpoint(anti_fake_code: str) -> tuple[str, str]:
    """Return (url, method) for HTML/Vue shell pages (legacy routing)."""
    code = anti_fake_code.strip()
    length = len(code)

    if length == 12 and not code.startswith("0") and not code.startswith("3001"):
        return (
            "http://www.scetia.com/Scetia.OnlineExplorer/App_Public/AntiFakeReportQuery.aspx",
            "POST",
        )
    if length == 10:
        return (
            "http://www.scetimis.com/QueryReport/SearchQueryReport.aspx",
            "POST",
        )
    if length == 12 and code.startswith("0"):
        return (f"https://rptverify.scetia.com/checkreport/?code={code}", "GET")
    if length == 11:
        return (f"https://rptverify.scetia.com/checkreport/?code={code}", "GET")
    if length == 12 and code.startswith("3001"):
        return (f"https://signboard.scetimis.com/checkreport?code={code}", "GET")

    return (
        "http://www.scetia.com/Scetia.OnlineExplorer/App_Public/AntiFakeReportQuery.aspx",
        "POST",
    )


def json_api_endpoint(backend: AssociationBackend) -> str:
    if backend == "rptverify_json":
        return RPTVERIFY_API
    if backend == "signboard_json":
        return SIGNBOARD_API
    raise ValueError(f"No JSON API for backend {backend}")


def extract_params_from_qr(qr_texts: list[str]) -> tuple[str | None, str | None]:
    from src.qr_decode import _extract_params_from_text

    report_no = None
    anti_fake = None
    for text in qr_texts:
        if not text:
            continue
        rn, af = _extract_params_from_text(text)
        report_no = report_no or rn
        anti_fake = anti_fake or af
        if report_no and anti_fake:
            return report_no, anti_fake
        parsed = urlparse(text)
        if parsed.query:
            qs = parse_qs(parsed.query)
            report_no = report_no or (qs.get("rqstConsignID") or [None])[0]
            anti_fake = anti_fake or (qs.get("rqstIdentifyingCode") or [None])[0]
            report_no = report_no or (qs.get("reportOrEntrustNo") or [None])[0]
            anti_fake = anti_fake or (qs.get("identifyingCode") or [None])[0]
    return report_no, anti_fake


def _decode_response(resp: requests.Response) -> str:
    """Decode response with proper encoding handling for GB2312/GBK pages."""
    encoding = resp.apparent_encoding
    if encoding:
        if encoding.lower() in ("gb2312", "gbk", "gb18030"):
            encoding = "gb18030"
        resp.encoding = encoding
    else:
        resp.encoding = resp.encoding or "utf-8"

    try:
        return resp.text
    except Exception:
        content = resp.content
        for enc in ("gb18030", "gbk", "gb2312", "utf-8"):
            try:
                return content.decode(enc)
            except Exception:
                continue
        return content.decode("utf-8", errors="replace")


def fetch_association_html(
    report_no: str,
    anti_fake_code: str,
    session: requests.Session | None = None,
) -> tuple[str, AssociationQuery]:
    url, method = resolve_endpoint(anti_fake_code)
    backend = resolve_association_backend(anti_fake_code)
    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", DEFAULT_UA)

    if method == "POST":
        params = {
            "rqstConsignID": report_no,
            "rqstIdentifyingCode": anti_fake_code,
            "rtURL": "http://www.scetia.com/AntiFakeReportQuery.asp",
        }
        data = {
            "rqstConsignID": report_no,
            "rqstIdentifyingCode": anti_fake_code,
        }
        resp = sess.post(url, params=params, data=data, timeout=TIMEOUT_POST)
    else:
        if "?" in url:
            resp = sess.get(url, timeout=TIMEOUT_GET)
        else:
            resp = sess.get(
                url,
                params={"rqstConsignID": report_no, "code": anti_fake_code},
                timeout=TIMEOUT_GET,
            )

    if resp.status_code >= 400:
        resp.raise_for_status()

    html = _decode_response(resp)
    query = AssociationQuery(
        report_no=report_no,
        anti_fake_code=anti_fake_code,
        endpoint=url,
        method=method,
        backend=backend,
    )
    return html, query


# Backward-compatible alias
fetch_association = fetch_association_html


def _scrape_association_json(
    backend: AssociationBackend,
    report_no: str,
    anti_fake: str,
    sess: requests.Session,
) -> dict[str, Any]:
    if backend == "rptverify_json":
        payload = fetch_rptverify_json(report_no, anti_fake, sess)
        if not is_rptverify_success(payload):
            msg = payload.get("resultMessage") or payload
            raise ValueError(f"rptverify API rejected query: {msg}")
    elif backend == "signboard_json":
        payload = fetch_signboard_json(report_no, anti_fake, sess)
        if not is_signboard_success(payload):
            msg = payload.get("resultMessage") or payload.get("message") or payload
            raise ValueError(f"signboard API rejected query: {msg}")
    else:
        raise ValueError(f"Not a JSON backend: {backend}")

    return api_response_to_report(
        payload,
        backend=backend,
        report_no=report_no,
        check_code=anti_fake,
    )


def _result_payload(
    decode: DecodeResult,
    query: AssociationQuery,
    project: dict[str, Any],
    samples: list[dict[str, Any]],
    *,
    report_pdf_url: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "source_image": decode.image,
        "report_type": "association",
        "qr_content": decode.qr_texts[0] if decode.qr_texts else "",
        "query": {
            "report_no": query.report_no,
            "anti_fake_code": query.anti_fake_code,
            "endpoint": query.endpoint,
            "method": query.method,
            "backend": query.backend,
        },
        "project": project,
        "samples": samples,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    if report_pdf_url:
        out["report_pdf_url"] = report_pdf_url
    return out


def scrape_association(
    decode: DecodeResult, session: requests.Session | None = None
) -> dict[str, Any]:
    report_no = decode.report_no
    anti_fake = decode.anti_fake_code
    if not report_no or not anti_fake:
        report_no, anti_fake = extract_params_from_qr(decode.qr_texts)
    if not report_no or not anti_fake:
        raise ValueError(
            f"Cannot extract report_no/anti_fake_code from QR: {decode.qr_texts}"
        )

    sess = session or requests.Session()
    sess.headers.setdefault("User-Agent", DEFAULT_UA)
    backend = resolve_association_backend(anti_fake)

    if backend in ("rptverify_json", "signboard_json"):
        parsed = _scrape_association_json(backend, report_no, anti_fake, sess)
        query = AssociationQuery(
            report_no=report_no,
            anti_fake_code=anti_fake,
            endpoint=json_api_endpoint(backend),
            method="POST",
            backend=backend,
        )
        return _result_payload(
            decode,
            query,
            parsed.get("project", {}),
            parsed.get("samples", []),
            report_pdf_url=parsed.get("report_pdf_url"),
        )

    last_error: Exception | None = None
    html = ""
    query: AssociationQuery | None = None

    for attempt in range(2):
        try:
            html, query = fetch_association_html(report_no, anti_fake, sess)
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                continue
            raise

    if query is None:
        raise last_error or RuntimeError("fetch_association_html failed")

    parsed = parse_association_html(html)
    return _result_payload(
        decode,
        query,
        parsed.get("project", {}),
        parsed.get("samples", []),
    )
