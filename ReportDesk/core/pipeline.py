"""Wrap ScanReport decode + scrape for ReportDesk."""

from __future__ import annotations

import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import requests

from .association_retry import all_retry_candidates

CODE_BASE = Path(__file__).resolve().parents[2]
SCAN_REPORT_ROOT = CODE_BASE / "ScanReport"


def _ensure_scanreport_path() -> None:
    root = str(SCAN_REPORT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def report_no_from_scrape(scrape: dict[str, Any], report_type: str | None) -> str | None:
    """ScanReport JSON 各渠道报告编号位置不一致（院网为 query.r_no / project.report_no）。"""
    q = scrape.get("query") or {}
    proj = scrape.get("project") or {}
    match = scrape.get("match") or {}
    if report_type == "institute":
        return proj.get("report_no") or q.get("r_no")
    if report_type == "association":
        return proj.get("report_no") or q.get("report_no")
    if report_type == "limis":
        return match.get("testingReportNo") or q.get("report_no")
    return (
        proj.get("report_no")
        or q.get("report_no")
        or q.get("r_no")
        or match.get("testingReportNo")
    )


@dataclass
class ProcessResult:
    status: Literal["success", "skipped", "failed"]
    source_image: str
    report_type: str | None = None
    report_no: str | None = None
    decode_method: str | None = None
    scrape: dict[str, Any] | None = None
    error: str | None = None
    decoded: Any | None = None  # ScanReport DecodeResult


@dataclass
class DecodeOutcome:
    status: Literal["success", "skipped", "failed"]
    source_image: str
    decoded: Any | None = None
    report_type: str | None = None
    report_no: str | None = None
    anti_fake_code: str | None = None
    decode_method: str | None = None
    qr_text: str = ""
    ocr_preview: str | None = None
    error: str | None = None


class ReportPipeline:
    def __init__(
        self,
        *,
        weights_folder: Path | None = None,
        ocr_dir: Path | None = None,
        ocr_enabled: bool = True,
        limis_client: Any | None = None,
        http_session: requests.Session | None = None,
    ) -> None:
        _ensure_scanreport_path()
        from src.decode_pipeline import decode_image_with_fallback  # type: ignore
        from src.qr_decode import get_qreader  # type: ignore
        from src.scrape_association import scrape_association  # type: ignore
        from src.scrape_institute import scrape_institute  # type: ignore
        from src.scrape_limis import create_limis_client, scrape_limis  # type: ignore

        self._decode = decode_image_with_fallback
        self._get_qreader = get_qreader
        self._scrape_association = scrape_association
        self._scrape_institute = scrape_institute
        self._scrape_limis = scrape_limis
        self._create_limis_client = create_limis_client

        self.weights_folder = weights_folder or SCAN_REPORT_ROOT
        self.ocr_dir = ocr_dir
        self.ocr_enabled = ocr_enabled
        self.limis_client = limis_client
        self.http_session = http_session or requests.Session()
        self._qreader_ready = False

    def ensure_qreader(self) -> None:
        if not self._qreader_ready:
            self._get_qreader(self.weights_folder)
            self._qreader_ready = True

    def decode_image(self, image_path: Path) -> DecodeOutcome:
        """仅解码（QR/OCR），不爬取。"""
        self.ensure_qreader()
        name = image_path.name
        try:
            decoded, err = self._decode(
                image_path,
                self.weights_folder,
                ocr_enabled=self.ocr_enabled,
                ocr_dir=self.ocr_dir,
            )
        except Exception as e:
            return DecodeOutcome("failed", name, error=f"decode error: {e}")

        if decoded is None:
            return DecodeOutcome("skipped", name, error=err or "no QR / OCR")

        qr_text = "\n".join(t for t in (decoded.qr_texts or []) if t)
        return DecodeOutcome(
            "success",
            name,
            decoded=decoded,
            report_type=decoded.report_type,
            report_no=decoded.report_no,
            anti_fake_code=decoded.anti_fake_code,
            decode_method=decoded.decode_source,
            qr_text=qr_text,
            ocr_preview=decoded.ocr_text_preview,
        )

    @staticmethod
    def _association_payload_ok(scrape: dict[str, Any]) -> bool:
        proj = scrape.get("project") or {}
        if (proj.get("project_name") or "").strip():
            return True
        if (proj.get("report_no") or "").strip() and scrape.get("samples"):
            return True
        return False

    def _scrape_association_with_retry(
        self,
        decoded: Any,
        session: requests.Session,
    ) -> dict[str, Any]:
        anti = (decoded.anti_fake_code or "").strip()
        if not anti:
            return self._scrape_association(decoded, session)

        primary = (decoded.report_no or "").strip()
        if not primary:
            return self._scrape_association(decoded, session)

        last_err: Exception | None = None
        last_scrape: dict[str, Any] | None = None
        for candidate in all_retry_candidates(primary):
            attempt = replace(decoded, report_no=candidate)
            try:
                scrape = self._scrape_association(attempt, session)
                if not self._association_payload_ok(scrape):
                    last_scrape = scrape
                    last_err = ValueError(
                        f"协会查询无工程数据（报告编号 {candidate!r} 可能 OCR 错误）"
                    )
                    continue
                resolved = report_no_from_scrape(scrape, "association") or candidate
                if resolved and resolved.upper() != candidate.upper():
                    scrape.setdefault("project", {})["report_no"] = resolved
                return scrape
            except Exception as e:
                last_err = e
                continue
        if last_err:
            raise last_err
        if last_scrape is not None:
            raise ValueError("协会爬取结果为空，请核对报告编号与防伪码")
        return self._scrape_association(decoded, session)

    def scrape_decoded(
        self,
        decoded: Any,
        *,
        limis_base: str | None = None,
        limis_user: str | None = None,
        limis_password: str | None = None,
        limis_auth_type: str | None = None,
        report_no: str | None = None,
        anti_fake_code: str | None = None,
    ) -> ProcessResult:
        """对已解码结果爬取；可覆盖报告编号/防伪码（人工或扫码枪）。"""
        name = decoded.image
        report_type = decoded.report_type
        if report_no:
            decoded = replace(decoded, report_no=report_no.strip())
        if anti_fake_code:
            decoded = replace(decoded, anti_fake_code=anti_fake_code.strip())

        try:
            if report_type == "association":
                scrape = self._scrape_association_with_retry(decoded, self.http_session)
            elif report_type == "limis":
                if self.limis_client is None:
                    self.limis_client = self._create_limis_client(
                        base_url=limis_base,
                        username=limis_user,
                        password=limis_password,
                        auth_type=limis_auth_type,
                    )
                    self.limis_client.login()
                scrape = self._scrape_limis(decoded, client=self.limis_client)
            elif report_type == "institute":
                scrape = self._scrape_institute(decoded, self.http_session)
            elif any(
                t.strip().lower().startswith(("http://", "https://"))
                for t in decoded.qr_texts
                if t
            ):
                scrape = self._scrape_institute(decoded, self.http_session)
                report_type = "institute"
            else:
                return ProcessResult(
                    "failed",
                    name,
                    report_type=report_type,
                    report_no=decoded.report_no,
                    decoded=decoded,
                    error=f"unknown type: {decoded.qr_texts}",
                )
            resolved_no = decoded.report_no or report_no_from_scrape(scrape, report_type)
            return ProcessResult(
                "success",
                name,
                report_type=report_type,
                report_no=resolved_no,
                decode_method=decoded.decode_source,
                scrape=scrape,
                decoded=decoded,
            )
        except Exception as e:
            return ProcessResult(
                "failed",
                name,
                report_type=report_type,
                report_no=decoded.report_no,
                decode_method=decoded.decode_source,
                decoded=decoded,
                error=str(e),
            )

    def process_image(
        self,
        image_path: Path,
        *,
        limis_base: str | None = None,
        limis_user: str | None = None,
        limis_password: str | None = None,
        limis_auth_type: str | None = None,
    ) -> ProcessResult:
        self.ensure_qreader()
        name = image_path.name
        try:
            decoded, err = self._decode(
                image_path,
                self.weights_folder,
                ocr_enabled=self.ocr_enabled,
                ocr_dir=self.ocr_dir,
            )
        except Exception as e:
            return ProcessResult("failed", name, error=f"decode error: {e}")

        if decoded is None:
            return ProcessResult("skipped", name, error=err or "no QR / OCR")

        report_type = decoded.report_type
        report_no = decoded.report_no

        try:
            if report_type == "association":
                scrape = self._scrape_association_with_retry(decoded, self.http_session)
            elif report_type == "limis":
                if self.limis_client is None:
                    self.limis_client = self._create_limis_client(
                        base_url=limis_base,
                        username=limis_user,
                        password=limis_password,
                        auth_type=limis_auth_type,
                    )
                    self.limis_client.login()
                scrape = self._scrape_limis(decoded, client=self.limis_client)
            elif report_type == "institute":
                scrape = self._scrape_institute(decoded, self.http_session)
            elif any(
                t.strip().lower().startswith(("http://", "https://"))
                for t in decoded.qr_texts
                if t
            ):
                scrape = self._scrape_institute(decoded, self.http_session)
                report_type = "institute"
            else:
                return ProcessResult(
                    "failed",
                    name,
                    report_type=report_type,
                    report_no=report_no,
                    error=f"unknown type: {decoded.qr_texts}",
                )
            resolved_no = report_no or report_no_from_scrape(scrape, report_type)
            return ProcessResult(
                "success",
                name,
                report_type=report_type,
                report_no=resolved_no,
                decode_method=decoded.decode_source,
                scrape=scrape,
                decoded=decoded,
            )
        except Exception as e:
            if report_no:
                return ProcessResult(
                    "failed",
                    name,
                    report_type=report_type,
                    report_no=report_no,
                    decode_method=decoded.decode_source,
                    decoded=decoded,
                    error=str(e),
                )
            return ProcessResult(
                "failed",
                name,
                decoded=decoded,
                error=str(e),
            )
