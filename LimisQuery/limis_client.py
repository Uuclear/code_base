"""LIMIS internal API client for integrated query (综合查询)."""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

DEFAULT_BASE = "http://10.1.228.22"
LOGIN_PATH = "/AjaxRequest/Index/HomeIndex.ashx"
INTEGRATED_ASHX = "/AjaxRequest/IntegratedQueryManage/IntegratedQuery.ashx"
TASK_ASHX = "/AjaxRequest/Task/Task.ashx"
REPORT_ASHX = "/AjaxRequest/report/testingReportQuery.ashx"
DETAIL_PAGE = "/UI/IntegratedQueryManage/IntegratedDetail.aspx"
INTEGRATED_UI = "/UI/IntegratedQueryManage/IntegratedQuery.html"

# IntegratedQuery.html「权限选择」radio（与页面一致）
AUTH_TYPE_LABELS: dict[str, str] = {
    "1": "样品主体",
    "2": "样品副体",
    "3": "任务",
    "4": "合同",
    "5": "综合(慢)",  # 页面已注释，接口可能仍可用
    "0": "未在页面展示；实测 CC018-260001 等需用此值才能在列表命中",
}
# 列表尝试顺序：先 CLI/config 指定值，再按此序（1→0→2→3→4→5）
INTEGRATED_AUTH_TYPE_ORDER: tuple[str, ...] = ("1", "0", "2", "3", "4", "5")


@dataclass
class LimisConfig:
    base_url: str = DEFAULT_BASE
    username: str = ""
    password: str = ""
    menu_id: str = "8"
    auth_type: str = "1"  # 默认与页面 checked 一致：样品主体
    timeout: int = 60


def _normalize_report_no(value: str) -> str:
    return value.strip().upper()


def _decode_html(resp: requests.Response) -> str:
    encoding = resp.apparent_encoding
    if encoding and encoding.lower() in ("gb2312", "gbk", "gb18030"):
        encoding = "gb18030"
    elif encoding:
        resp.encoding = encoding
    else:
        resp.encoding = resp.encoding or "utf-8"
    try:
        return resp.text
    except Exception:
        for enc in ("gb18030", "gbk", "gb2312", "utf-8"):
            try:
                return resp.content.decode(enc)
            except Exception:
                continue
        return resp.content.decode("utf-8", errors="replace")


def html_table_fields(html: str) -> dict[str, str]:
    """Extract label/value pairs from HTML tables."""
    soup = BeautifulSoup(html, "lxml")
    fields: dict[str, str] = {}
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            fields[cells[0]] = cells[1]
        elif len(cells) == 1 and cells[0] not in fields:
            fields[cells[0]] = ""
    return fields


class LimisClient:
    def __init__(self, config: LimisConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                ),
            }
        )
        base = config.base_url.rstrip("/") + "/"
        self._referer = urljoin(
            base, f"UI/IntegratedQueryManage/IntegratedQuery.html?menuId={config.menu_id}"
        )
        self._detail_referer = urljoin(base, DETAIL_PAGE.lstrip("/"))
        self.session.headers["Referer"] = self._referer
        self._logged_in = False

    @staticmethod
    def encode_password(plain: str) -> str:
        return base64.b64encode(plain.encode("utf-8")).decode("ascii")

    def _url(self, path: str) -> str:
        return urljoin(self.config.base_url.rstrip("/") + "/", path.lstrip("/"))

    def bootstrap(self) -> None:
        self.session.get(self._referer, timeout=self.config.timeout)

    def login(self) -> dict[str, Any]:
        self.bootstrap()
        resp = self.session.post(
            self._url(LOGIN_PATH),
            data={
                "method": "Login",
                "username": self.config.username,
                "pwd": self.encode_password(self.config.password),
            },
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("state") != "1":
            raise RuntimeError(f"Login failed: {data}")
        self._logged_in = True
        return data

    def _ensure_login(self) -> None:
        if not self._logged_in:
            self.login()

    def _empty_query_fields(self) -> dict[str, str]:
        return {
            "testingOrderNo": "",
            "testingOrderUnit": "",
            "testingSamplesNo": "",
            "testingReportsNo": "",
            "testingType": "",
            "productType": "",
            "testingType2": "",
            "TestBasisCode": "",
            "TestBasisName": "",
            "ProjectName": "",
            "testingOrderTypeDesp": "",
            "zhuti": "",
            "creator": "",
            "projectSection": "",
            "DelegateTimeS": "",
            "DelegateTimeE": "",
            "TestingMechanism": "",
            "SampleName": "",
            "Manufacturer": "",
            "TypeSpecification": "",
            "GenerationDateS": "",
            "GenerationDateE": "",
            "ReportProperties": "",
            "Reviewer": "",
            "Approver": "",
            "testingOrderContractNo": "",
            "testingOrderContractNo2": "",
            "contractIndex": "",
        }

    def integrated_query(
        self,
        *,
        testing_reports_no: str = "",
        testing_order_no: str = "",
        page: int = 1,
        size: int = 50,
        auth_type: str | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_login()
        at = auth_type if auth_type is not None else self.config.auth_type
        data = {
            "method": "GetIntegratedQueryInfo",
            "type": "4",
            "size": str(size),
            "page": str(page),
            "cha": "1",
            "authType": at,
            **self._empty_query_fields(),
        }
        if testing_reports_no:
            data["testingReportsNo"] = testing_reports_no.strip()
        if testing_order_no:
            data["testingOrderNo"] = testing_order_no.strip()

        resp = self.session.post(
            self._url(INTEGRATED_ASHX),
            data=data,
            timeout=self.config.timeout,
        )
        if resp.status_code >= 400 or resp.text.lstrip().startswith("<"):
            raise RuntimeError(
                f"Integrated query HTTP {resp.status_code}: {resp.text[:300]}"
            )
        if not resp.text.strip():
            return []
        return json.loads(resp.text)

    def get_tasks(self, testing_order_id: int | str) -> list[dict[str, Any]]:
        self._ensure_login()
        resp = self.session.post(
            self._url(TASK_ASHX),
            data={"method": "GetTaskInfo", "testingOrderId": str(testing_order_id)},
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        if not resp.text.strip():
            return []
        return json.loads(resp.text)

    def fetch_html_page(self, path: str) -> dict[str, Any]:
        """GET a UI/FileUpload path; return url, fields, text preview."""
        self._ensure_login()
        url = self._url(path)
        prev_referer = self.session.headers.get("Referer")
        self.session.headers["Referer"] = self._detail_referer
        try:
            resp = self.session.get(url, timeout=self.config.timeout)
            resp.raise_for_status()
            html = _decode_html(resp)
        finally:
            if prev_referer:
                self.session.headers["Referer"] = prev_referer

        fields = html_table_fields(html)
        text = BeautifulSoup(html, "lxml").get_text("\n", strip=True)
        return {
            "url": url,
            "html_length": len(html),
            "fields": fields,
            "text": text,
        }

    def search_pdf(self, report_id: int | str) -> dict[str, Any]:
        self._ensure_login()
        resp = self.session.post(
            self._url(REPORT_ASHX),
            data={"method": "SearchPDF", "reportId": str(report_id)},
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def copy_pdf(self, report_id: int | str) -> dict[str, Any]:
        self._ensure_login()
        resp = self.session.post(
            self._url(REPORT_ASHX),
            data={"method": "CopyPDF", "reportId": str(report_id), "v": "1"},
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def report_audit_history(self, report_id: int | str) -> list[dict[str, Any]]:
        self._ensure_login()
        resp = self.session.post(
            self._url(INTEGRATED_ASHX),
            data={
                "method": "testingReportHistoryInfo",
                "testingReportId": str(report_id),
            },
            timeout=self.config.timeout,
        )
        if not resp.text.strip():
            return []
        return json.loads(resp.text)

    def parse_detail_page(
        self, testing_order_id: int | str, target_report_no: str | None = None
    ) -> dict[str, Any]:
        """
        Parse IntegratedDetail.aspx left tree and hidden fields.
        If target_report_no set, only that report (exact match) is flagged.
        """
        self._ensure_login()
        oid = str(testing_order_id)
        url = self._url(DETAIL_PAGE)
        prev_referer = self.session.headers.get("Referer")
        self.session.headers["Referer"] = self._detail_referer
        try:
            resp = self.session.get(
                url, params={"testingOrderId": oid}, timeout=self.config.timeout
            )
            resp.raise_for_status()
            html = _decode_html(resp)
        finally:
            if prev_referer:
                self.session.headers["Referer"] = prev_referer

        detail_url = f"{url}?testingOrderId={oid}"
        meta: dict[str, str] = {}
        for hid, val in re.findall(r'id="(hd[^"]+)"[^>]*value="([^"]*)"', html):
            meta[hid] = val

        samples: list[dict[str, str]] = []
        for sample_id, label in re.findall(
            r"ShowSamples\(['\"](\d+)['\"]\).*?<span[^>]*>([^<]+)</span>",
            html,
            flags=re.S,
        ):
            samples.append({"sampleId": sample_id, "label": label.strip()})

        reports: list[dict[str, Any]] = []
        for block in re.finditer(
            r"ShowReport\(([^,]+),this\)[^>]*data-id=[\"'](\d+)[\"'][^>]*"
            r"data-sampleid=[\"'](\d+)[\"'][^>]*data-value=[\"']([^\"']+)[\"'][^>]*>"
            r"[\s\S]*?<span[^>]*>[\s\S]*?</i>\s*([^<]+)</span>",
            html,
            flags=re.S,
        ):
            onclick_arg, report_id, sample_id, report_no, status_label = block.groups()
            onclick_arg = onclick_arg.strip().strip("'\"")
            report_no = report_no.strip()
            status_label = status_label.strip()
            status_m = re.search(r"\(([^)]+)\)\s*$", status_label)
            entry: dict[str, Any] = {
                "testingReportId": report_id,
                "testingReportNo": report_no,
                "sampleId": sample_id,
                "status": status_m.group(1) if status_m else "",
                "label": status_label,
                "onclick": onclick_arg.strip("'"),
            }
            if target_report_no:
                entry["exact_match"] = (
                    _normalize_report_no(report_no) == _normalize_report_no(target_report_no)
                )
            reports.append(entry)

        # Fallback: simpler data-id/data-value parse
        if not reports:
            for report_id, report_no in re.findall(
                r'data-id="(\d+)"[^>]*data-value="([^"]+)"', html
            ):
                entry = {
                    "testingReportId": report_id,
                    "testingReportNo": report_no.strip(),
                    "sampleId": "",
                    "status": "",
                    "label": report_no,
                    "onclick": "",
                }
                if target_report_no:
                    entry["exact_match"] = (
                        _normalize_report_no(report_no)
                        == _normalize_report_no(target_report_no)
                    )
                reports.append(entry)

        raw_links: list[dict[str, str]] = []
        for m in re.finditer(r"ShowReport\(['\"]([^'\"]+)['\"](?:,this)?\)", html):
            raw = m.group(1)
            path = raw
            if path.startswith("../../"):
                path = "/" + path[6:]
            elif path.startswith("../"):
                path = "/UI/" + path[3:]
            raw_links.append({"path": path, "raw": raw})

        return {
            "detail_url": detail_url,
            "testingOrderId": int(oid),
            "testingOrderNo": meta.get("hdtestingOrderNo", ""),
            "meta": meta,
            "samples": samples,
            "reports": reports,
            "raw_delegation_link": next(
                (x for x in raw_links if "TestingOrderHtml" in x["path"]), None
            ),
        }

    def fetch_order_detail_bundle(
        self,
        testing_order_id: int | str,
        report: dict[str, Any],
    ) -> dict[str, Any]:
        """Fetch detail page tree + embedded pages for the matched report."""
        oid = str(testing_order_id)
        detail = self.parse_detail_page(oid, target_report_no=report["testingReportNo"])
        bundle: dict[str, Any] = {
            "detail": detail,
            "tasks": self.get_tasks(oid),
            "report": dict(report),
            "pages": {},
        }

        rid = report["testingReportId"]
        sid = report.get("sampleId") or ""

        try:
            bundle["report"]["pdf"] = self.search_pdf(rid)
            if not (bundle["report"]["pdf"].get("url")):
                bundle["report"]["copy_pdf"] = self.copy_pdf(rid)
        except Exception as exc:  # noqa: BLE001
            bundle["report"]["pdf"] = {"error": str(exc)}

        try:
            bundle["report"]["audit_history"] = self.report_audit_history(rid)
        except Exception as exc:  # noqa: BLE001
            bundle["report"]["audit_history"] = {"error": str(exc)}

        link = detail.get("raw_delegation_link")
        if link:
            try:
                bundle["pages"]["raw_delegation"] = self.fetch_html_page(link["path"])
            except Exception as exc:  # noqa: BLE001
                bundle["pages"]["raw_delegation"] = {"error": str(exc)}

        try:
            bundle["pages"]["order_print"] = self.fetch_html_page(
                f"/UI/TestingOrder/PrintTestingOrderReplace.aspx?testingOrderId={oid}"
            )
        except Exception as exc:  # noqa: BLE001
            bundle["pages"]["order_print"] = {"error": str(exc)}

        if sid:
            try:
                bundle["pages"]["sample_detail"] = self.fetch_html_page(
                    f"/UI/TestingOrder/SamplesDetail.html?sampleid={sid}"
                )
            except Exception as exc:  # noqa: BLE001
                bundle["pages"]["sample_detail"] = {"error": str(exc)}

        onclick = report.get("onclick") or ""
        if "WaitBuild.aspx" in onclick:
            path = onclick
            if path.startswith("../"):
                path = "/UI/" + path[3:]
            try:
                bundle["pages"]["report_waitbuild"] = self.fetch_html_page(path)
            except Exception as exc:  # noqa: BLE001
                bundle["pages"]["report_waitbuild"] = {"error": str(exc)}

        return bundle

    def _auth_type_try_sequence(self) -> tuple[str, ...]:
        """Preferred auth_type first, then INTEGRATED_AUTH_TYPE_ORDER without duplicates."""
        preferred = self.config.auth_type
        seen: set[str] = set()
        sequence: list[str] = []
        for at in (preferred, *INTEGRATED_AUTH_TYPE_ORDER):
            if at not in seen:
                seen.add(at)
                sequence.append(at)
        return tuple(sequence)

    def _integrated_query_with_auth_fallback(
        self,
        *,
        testing_reports_no: str,
        page_size: int,
        page: int = 1,
    ) -> tuple[str, list[dict[str, Any]], dict[str, Any] | None]:
        """Try auth types in order 1,0,2,3,4,5 (config value first) until rows returned."""
        list_auth = self.config.auth_type
        auth_note: dict[str, Any] | None = None
        rows: list[dict[str, Any]] = []
        for at in self._auth_type_try_sequence():
            rows = self.integrated_query(
                testing_reports_no=testing_reports_no,
                size=page_size,
                page=page,
                auth_type=at,
            )
            if rows:
                list_auth = at
                if at != self.config.auth_type:
                    auth_note = {
                        "list_auth_type": at,
                        "list_auth_label": AUTH_TYPE_LABELS.get(at, at),
                        "fallback_from": self.config.auth_type,
                    }
                break
        return list_auth, rows, auth_note

    def collect_candidate_order_ids(
        self,
        report_no: str,
        *,
        max_suffix_pages: int = 5,
        page_size: int = 100,
    ) -> tuple[list[int], list[dict[str, Any]], str]:
        """Gather order IDs from list API (fuzzy); exact match done on detail page."""
        notes: list[dict[str, Any]] = []
        seen: set[int] = set()
        ordered: list[int] = []

        def add_from_rows(rows: list[dict[str, Any]], strategy: str) -> None:
            notes.append({"strategy": strategy, "list_rows": len(rows)})
            for row in rows:
                oid = row.get("testingOrderId")
                if oid is None:
                    continue
                ioid = int(oid)
                if ioid not in seen:
                    seen.add(ioid)
                    ordered.append(ioid)

        list_auth, rows, auth_note = self._integrated_query_with_auth_fallback(
            testing_reports_no=report_no, page_size=page_size
        )
        if auth_note:
            notes.append(auth_note)
        add_from_rows(rows, "testingReportsNo")

        suffix_m = re.search(r"-(\d{5,})$", report_no)
        if suffix_m:
            suffix = suffix_m.group(1)
            for page in range(1, max_suffix_pages + 1):
                batch = self.integrated_query(
                    testing_reports_no=suffix,
                    page=page,
                    size=page_size,
                    auth_type=list_auth,
                )
                if not batch:
                    break
                add_from_rows(batch, f"testingReportsNo_suffix_page_{page}")

        return ordered, notes, list_auth

    def find_exact_report(
        self,
        report_no: str,
        *,
        max_orders_to_scan: int = 30,
        max_suffix_pages: int = 5,
        page_size: int = 100,
    ) -> dict[str, Any]:
        """
        Find the unique order whose IntegratedDetail tree contains report_no
        with an exact match (报告编号唯一).
        """
        target = report_no.strip()
        target_norm = _normalize_report_no(target)

        result: dict[str, Any] = {
            "query": {"report_no": target},
            "login": None,
            "match": {"found": False},
            "integrated_list_notes": [],
            "scan": {"orders_checked": 0, "order_ids_tried": []},
            "detail": None,
            "notes": [],
        }

        if not self._logged_in:
            result["login"] = self.login()
        else:
            result["login"] = {"state": "1", "reused_session": True}
        order_ids, list_notes, list_auth = self.collect_candidate_order_ids(
            target, max_suffix_pages=max_suffix_pages, page_size=page_size
        )
        result["query"]["auth_type"] = list_auth
        result["query"]["auth_type_label"] = AUTH_TYPE_LABELS.get(list_auth, list_auth)
        result["integrated_list_notes"] = list_notes

        integrated_row: dict[str, Any] | None = None
        matched_report: dict[str, Any] | None = None
        matched_order_id: int | None = None

        for idx, oid in enumerate(order_ids[:max_orders_to_scan]):
            result["scan"]["order_ids_tried"].append(oid)
            result["scan"]["orders_checked"] = idx + 1

            detail = self.parse_detail_page(oid, target_report_no=target)
            exact_reports = [
                r
                for r in detail["reports"]
                if _normalize_report_no(r["testingReportNo"]) == target_norm
            ]
            if not exact_reports:
                continue
            if len(exact_reports) > 1:
                result["notes"].append(
                    f"委托 {oid} 详情树中存在多条编号为 {target} 的报告，已取第一条。"
                )
            matched_report = exact_reports[0]
            matched_order_id = oid

            list_rows = self.integrated_query(
                testing_reports_no=target, size=page_size, auth_type=list_auth
            )
            for row in list_rows:
                if int(row.get("testingOrderId", -1)) == oid:
                    integrated_row = row
                    break
            if integrated_row is None:
                rows = self.integrated_query(
                    testing_order_no=detail["testingOrderNo"],
                    size=page_size,
                    auth_type=list_auth,
                )
                integrated_row = rows[0] if rows else None

            break

        if not matched_report or matched_order_id is None:
            result["notes"].append(
                "综合查询列表可能返回多条候选委托，但在详情页树中未找到与输入完全一致的报告编号。"
            )
            return result

        report_status = matched_report.get("status") or ""
        if not report_status and matched_report.get("label"):
            sm = re.search(r"\(([^)]+)\)\s*$", matched_report["label"])
            report_status = sm.group(1) if sm else ""

        result["match"] = {
            "found": True,
            "testingReportNo": matched_report["testingReportNo"],
            "testingReportId": matched_report["testingReportId"],
            "testingOrderId": matched_order_id,
            "testingOrderNo": detail["testingOrderNo"],
            "detail_url": detail["detail_url"],
            "report_status": report_status,
        }
        result["integrated_list_row"] = integrated_row
        result["detail"] = self.fetch_order_detail_bundle(
            matched_order_id, matched_report
        )
        result["notes"].append(
            "报告编号以 IntegratedDetail.aspx 左侧树 data-value 为准做全字匹配；"
            "综合查询列表仅用于收集候选 testingOrderId。"
        )
        return result

    # Backward-compatible alias
    def find_by_report_number(self, report_no: str, **kwargs: Any) -> dict[str, Any]:
        return self.find_exact_report(report_no, **kwargs)
