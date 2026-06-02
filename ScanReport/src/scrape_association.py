"""Scrape SCETIA association reports via anti-fake query endpoints."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from src.parse_html import parse_association_html
from src.qr_decode import DecodeResult

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT_POST = 60
TIMEOUT_GET = 30


@dataclass
class AssociationQuery:
    report_no: str
    anti_fake_code: str
    endpoint: str
    method: str


def resolve_endpoint(anti_fake_code: str) -> tuple[str, str]:
    """Return (url, method) based on anti-fake code rules from scetia JS."""
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

    # Default to material POST endpoint
    return (
        "http://www.scetia.com/Scetia.OnlineExplorer/App_Public/AntiFakeReportQuery.aspx",
        "POST",
    )


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
    return report_no, anti_fake


def _decode_response(resp: requests.Response) -> str:
    if resp.encoding:
        resp.encoding = resp.apparent_encoding or resp.encoding
    try:
        return resp.text
    except Exception:
        return resp.content.decode("utf-8", errors="replace")


def fetch_association(
    report_no: str,
    anti_fake_code: str,
    session: requests.Session | None = None,
) -> tuple[str, AssociationQuery]:
    url, method = resolve_endpoint(anti_fake_code)
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
    )
    return html, query


def scrape_association(decode: DecodeResult, session: requests.Session | None = None) -> dict[str, Any]:
    report_no = decode.report_no
    anti_fake = decode.anti_fake_code
    if not report_no or not anti_fake:
        report_no, anti_fake = extract_params_from_qr(decode.qr_texts)
    if not report_no or not anti_fake:
        raise ValueError(
            f"Cannot extract report_no/anti_fake_code from QR: {decode.qr_texts}"
        )

    sess = session or requests.Session()
    last_error: Exception | None = None
    html = ""
    query: AssociationQuery | None = None

    for attempt in range(2):
        try:
            html, query = fetch_association(report_no, anti_fake, sess)
            break
        except Exception as e:
            last_error = e
            if attempt == 0:
                continue
            raise

    if query is None:
        raise last_error or RuntimeError("fetch_association failed")

    parsed = parse_association_html(html)
    return {
        "source_image": decode.image,
        "report_type": "association",
        "qr_content": decode.qr_texts[0] if decode.qr_texts else "",
        "query": {
            "report_no": query.report_no,
            "anti_fake_code": query.anti_fake_code,
            "endpoint": query.endpoint,
            "method": query.method,
        },
        "project": parsed.get("project", {}),
        "samples": parsed.get("samples", []),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
