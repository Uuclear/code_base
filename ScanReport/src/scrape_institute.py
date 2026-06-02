"""Scrape institute (院网 jktac) reports via GetReportInfo API after rId numDecode."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qs, urlparse

import requests

from src.jktac_codec import decode_report_id
from src.parse_institute_api import api_response_to_report
from src.qr_decode import ASSOCIATION_HOSTS, DecodeResult

DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
PAGE_TIMEOUT = 60
API_TIMEOUT = 120
API_RETRIES = 4
API_RETRY_DELAY = 3.0

# Hosts known to use /WeChat/rQuery + GetReportInfo
JKTAC_API_PATH = "/WeChat/GetReportInfo"


def pick_institute_url(qr_texts: list[str]) -> str:
    for text in qr_texts:
        if not text:
            continue
        lower = text.strip().lower()
        if not lower.startswith(("http://", "https://")):
            continue
        if any(host in lower for host in ASSOCIATION_HOSTS):
            continue
        return text.strip()
    raise ValueError(f"No institute URL in QR texts: {qr_texts}")


def parse_jktac_query(url: str) -> tuple[str, str, str]:
    """Return (origin, rid_raw, rno)."""
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    rid = (qs.get("rId") or qs.get("rid") or [""])[0]
    rno = (qs.get("rNo") or qs.get("rno") or [""])[0]
    if not rid or not rno:
        raise ValueError(f"Missing rId/rNo in institute URL: {url}")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return origin, rid, rno


def _parse_api_response(resp: requests.Response) -> dict[str, Any] | None:
    text = resp.text.strip()
    if resp.status_code != 200:
        return None
    if text.startswith("{"):
        data = resp.json()
        if isinstance(data, dict) and data.get("testingReportNo"):
            return data
        return None
    # ASP.NET may return JSON string: "报告不存在"
    if text.startswith('"') and text.endswith('"'):
        return None
    return None


def fetch_report_info(
    origin: str,
    rid_raw: str,
    report_no: str,
    session: requests.Session,
) -> tuple[dict[str, Any], str]:
    """
    POST /WeChat/GetReportInfo. Per handle.js, rId should be numDecode(rId, 2);
    some deployments still accept the obfuscated rId — try decoded first, then raw.
    """
    page_url = f"{origin}/WeChat/rQuery?rId={rid_raw}&rNo={report_no}"
    api_url = f"{origin}{JKTAC_API_PATH}"

    session.headers.setdefault("User-Agent", DEFAULT_UA)
    session.get(page_url, timeout=PAGE_TIMEOUT)

    decoded_id = decode_report_id(rid_raw)
    # handle.js: ajax({ testingReportId, testingReportNo }, ..., GetReportInfo)
    id_candidates: list[tuple[str, str]] = [
        ("decoded", decoded_id),
        ("raw", rid_raw),
    ]

    headers = {
        "Referer": page_url,
        "X-Requested-With": "XMLHttpRequest",
    }

    last_error: Exception | None = None
    for id_kind, testing_report_id in id_candidates:
        payload = {
            "testingReportId": testing_report_id,
            "testingReportNo": report_no,
        }
        for attempt in range(API_RETRIES):
            try:
                resp = session.post(
                    api_url,
                    data=payload,
                    headers=headers,
                    timeout=API_TIMEOUT,
                )
                data = _parse_api_response(resp)
                if data:
                    return data, id_kind
                last_error = RuntimeError(
                    f"HTTP {resp.status_code} ({id_kind} id): {resp.text.strip()[:200]}"
                )
            except Exception as e:
                last_error = e
            if attempt < API_RETRIES - 1:
                time.sleep(API_RETRY_DELAY * (attempt + 1))

    raise last_error or RuntimeError("GetReportInfo failed after retries")


def scrape_institute(
    decode: DecodeResult,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    url = pick_institute_url(decode.qr_texts)
    origin, rid_raw, report_no = parse_jktac_query(url)
    sess = session or requests.Session()

    api_data, id_kind = fetch_report_info(origin, rid_raw, report_no, sess)
    parsed = api_response_to_report(api_data)
    report_id_decoded = decode_report_id(rid_raw)

    return {
        "source_image": decode.image,
        "report_type": "institute",
        "qr_content": url,
        "query": {
            "url": url,
            "host": urlparse(url).netloc,
            "r_id_raw": rid_raw,
            "r_id_decoded": report_id_decoded,
            "r_id_sent_as": id_kind,
            "r_no": report_no,
            "api": f"{origin}{JKTAC_API_PATH}",
        },
        "project": parsed["project"],
        "samples": parsed["samples"],
        "testing_result": parsed.get("testing_result"),
        "conclusion": parsed.get("conclusion"),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
