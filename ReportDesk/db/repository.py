"""Data access layer for ReportDesk."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .connection import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Repository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    @classmethod
    def open(cls, db_path: str | None = None) -> Repository:
        return cls(get_connection(db_path))

    def close(self) -> None:
        self.conn.close()

    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute(
            "SELECT value FROM app_settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str | None) -> None:
        if value is None:
            self.conn.execute("DELETE FROM app_settings WHERE key = ?", (key,))
        else:
            self.conn.execute(
                """
                INSERT INTO app_settings (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )
        self.conn.commit()

    def get_settings(self, keys: list[str]) -> dict[str, str | None]:
        return {k: self.get_setting(k) for k in keys}

    def allocate_file_index(self, report_no: str) -> int:
        """Next file index for report_no (1-based; every file gets -N suffix)."""
        row = self.conn.execute(
            "SELECT COALESCE(MAX(file_index), 0) AS mx FROM report_files WHERE report_no = ?",
            (report_no,),
        ).fetchone()
        return int(row["mx"]) + 1

    def upsert_report(self, row: dict[str, Any]) -> None:
        report_no = row["report_no"]
        existing = self.conn.execute(
            "SELECT created_at FROM reports WHERE report_no = ?", (report_no,)
        ).fetchone()
        created_at = existing["created_at"] if existing else _now()
        cols = [
            "report_no",
            "source_channel",
            "decode_method",
            "scrape_status",
            "order_no",
            "testing_report_id",
            "testing_order_id",
            "anti_fake_code",
            "institute_r_id_raw",
            "project_name",
            "project_address",
            "project_part",
            "section_folder",
            "project_section_extra",
            "project_serial_no",
            "unit_name",
            "unit_code",
            "institute_name",
            "institute_address",
            "institute_phone",
            "institute_postcode",
            "construction_unit",
            "witness_unit",
            "sampler",
            "witness",
            "contract_no",
            "total_fee",
            "consign_date",
            "report_date",
            "testing_date",
            "sampling_date",
            "order_time",
            "report_status",
            "consign_type",
            "testing_type_code",
            "testing_type_name",
            "change_status",
            "testing_result",
            "conclusion_summary",
            "scrape_json",
            "scraped_at",
            "organize_project_dir",
            "organize_section_dir",
        ]
        data = {c: row.get(c) for c in cols}
        data["created_at"] = created_at
        data["updated_at"] = _now()
        placeholders = ", ".join("?" for _ in cols + ["created_at", "updated_at"])
        names = ", ".join(cols + ["created_at", "updated_at"])
        updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "report_no")
        updates += ", updated_at=excluded.updated_at"
        values = [data[c] for c in cols] + [data["created_at"], data["updated_at"]]
        self.conn.execute(
            f"""
            INSERT INTO reports ({names}) VALUES ({placeholders})
            ON CONFLICT(report_no) DO UPDATE SET {updates}
            """,
            values,
        )
        self.conn.commit()

    def insert_report_file(
        self,
        report_no: str,
        file_index: int,
        original_path: str,
        stored_path: str | None,
        original_filename: str | None = None,
        file_hash: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO report_files
                (report_no, file_index, original_path, stored_path, original_filename, file_hash)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (report_no, file_index, original_path, stored_path, original_filename, file_hash),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def replace_samples(self, report_no: str, samples: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM report_samples WHERE report_no = ?", (report_no,))
        for i, s in enumerate(samples):
            s = dict(s)
            extra = s.pop("extra_json", None)
            if extra is not None and not isinstance(extra, str):
                extra = json.dumps(extra, ensure_ascii=False)
            self.conn.execute(
                """
                INSERT INTO report_samples (
                    report_no, seq, sample_no, sample_name, specification, grade,
                    project_part, exam_result, testing_date, manufacturer,
                    delegate_quantity, molding_date, age_time, extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_no,
                    i,
                    s.get("sample_no"),
                    s.get("sample_name"),
                    s.get("specification"),
                    s.get("grade"),
                    s.get("project_part"),
                    s.get("exam_result"),
                    s.get("testing_date"),
                    s.get("manufacturer"),
                    s.get("delegate_quantity"),
                    s.get("molding_date"),
                    s.get("age_time"),
                    extra,
                ),
            )
        self.conn.commit()

    def replace_tasks(self, report_no: str, tasks: list[dict[str, Any]]) -> None:
        self.conn.execute("DELETE FROM report_tasks WHERE report_no = ?", (report_no,))
        for t in tasks:
            raw = t.get("raw_json")
            if raw is not None and not isinstance(raw, str):
                raw = json.dumps(raw, ensure_ascii=False)
            self.conn.execute(
                """
                INSERT INTO report_tasks (
                    report_no, task_id, sample_id, task_name, sample_no, sample_name,
                    task_status_name, dept_name, editor, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report_no,
                    t.get("task_id"),
                    t.get("sample_id"),
                    t.get("task_name"),
                    t.get("sample_no"),
                    t.get("sample_name"),
                    t.get("task_status_name"),
                    t.get("dept_name"),
                    t.get("editor"),
                    raw,
                ),
            )
        self.conn.commit()

    def replace_audit_history(self, report_no: str, items: list[dict[str, Any]]) -> None:
        self.conn.execute(
            "DELETE FROM report_audit_history WHERE report_no = ?", (report_no,)
        )
        for a in items:
            raw = a.get("raw_json")
            if raw is not None and not isinstance(raw, str):
                raw = json.dumps(raw, ensure_ascii=False)
            self.conn.execute(
                """
                INSERT INTO report_audit_history
                    (report_no, audit_user_name, audit_result, create_time, raw_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    report_no,
                    a.get("audit_user_name"),
                    a.get("audit_result"),
                    a.get("create_time"),
                    raw,
                ),
            )
        self.conn.commit()

    def upsert_integrated_list_row(self, report_no: str, row: dict[str, Any]) -> None:
        if not row:
            return
        self.conn.execute(
            """
            INSERT INTO integrated_list_row (
                report_no, testing_order_id, testing_order_no, testing_order_contract_no,
                testing_order_unit_name, testing_order_unit_code, project_name,
                testing_institute_name, testing_type_code, testing_order_type_desp,
                testing_order_status_code, testing_order_time, sampling_date, total_fee,
                sample_count, report_count, change_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(report_no) DO UPDATE SET
                testing_order_id=excluded.testing_order_id,
                testing_order_no=excluded.testing_order_no,
                testing_order_contract_no=excluded.testing_order_contract_no,
                testing_order_unit_name=excluded.testing_order_unit_name,
                testing_order_unit_code=excluded.testing_order_unit_code,
                project_name=excluded.project_name,
                testing_institute_name=excluded.testing_institute_name,
                testing_type_code=excluded.testing_type_code,
                testing_order_type_desp=excluded.testing_order_type_desp,
                testing_order_status_code=excluded.testing_order_status_code,
                testing_order_time=excluded.testing_order_time,
                sampling_date=excluded.sampling_date,
                total_fee=excluded.total_fee,
                sample_count=excluded.sample_count,
                report_count=excluded.report_count,
                change_status=excluded.change_status
            """,
            (
                report_no,
                row.get("testing_order_id") or row.get("testingOrderId"),
                row.get("testing_order_no") or row.get("testingOrderNo"),
                row.get("testing_order_contract_no") or row.get("testingOrderContractNo"),
                row.get("testing_order_unit_name") or row.get("testingOrderUnitName"),
                row.get("testing_order_unit_code") or row.get("testingOrderUnitCode"),
                row.get("project_name") or row.get("projectName"),
                row.get("testing_institute_name") or row.get("testingInstituteName"),
                row.get("testing_type_code") or row.get("testingTypeCode"),
                row.get("testing_order_type_desp") or row.get("testingOrderTypeDesp"),
                row.get("testing_order_status_code") or row.get("testingOrderStatusCode"),
                row.get("testing_order_time") or row.get("testingOrderTime"),
                row.get("sampling_date") or row.get("samplingDate"),
                row.get("total_fee") if row.get("total_fee") is not None else row.get("totalFee"),
                row.get("sample_count") if row.get("sample_count") is not None else row.get("sampleCount"),
                row.get("report_count") if row.get("report_count") is not None else row.get("reportCount"),
                row.get("change_status") or row.get("changeStatus"),
            ),
        )
        self.conn.commit()

    def create_batch_job(self, total: int, output_root: str | None) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO batch_jobs (started_at, total_count, output_root)
            VALUES (?, ?, ?)
            """,
            (_now(), total, output_root),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def finish_batch_job(
        self,
        job_id: int,
        *,
        success: int,
        failed: int,
        skipped: int,
    ) -> None:
        self.conn.execute(
            """
            UPDATE batch_jobs SET
                finished_at = ?,
                success_count = ?,
                failed_count = ?,
                skipped_count = ?
            WHERE id = ?
            """,
            (_now(), success, failed, skipped, job_id),
        )
        self.conn.commit()

    def add_batch_item(
        self,
        job_id: int,
        image_path: str,
        status: str = "pending",
    ) -> int:
        cur = self.conn.execute(
            """
            INSERT INTO batch_job_items (job_id, image_path, status)
            VALUES (?, ?, ?)
            """,
            (job_id, image_path, status),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_batch_item(
        self,
        item_id: int,
        *,
        status: str,
        report_no: str | None = None,
        error_message: str | None = None,
        file_index: int | None = None,
        stored_path: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            UPDATE batch_job_items SET
                status = ?,
                report_no = COALESCE(?, report_no),
                error_message = ?,
                file_index = COALESCE(?, file_index),
                stored_path = COALESCE(?, stored_path),
                finished_at = ?
            WHERE id = ?
            """,
            (status, report_no, error_message, file_index, stored_path, _now(), item_id),
        )
        self.conn.commit()

    def save_normalized_bundle(self, bundle: dict[str, Any]) -> None:
        """Persist report row and child tables from normalize output."""
        self.upsert_report(bundle["report"])
        if bundle.get("samples"):
            self.replace_samples(bundle["report"]["report_no"], bundle["samples"])
        if bundle.get("tasks"):
            self.replace_tasks(bundle["report"]["report_no"], bundle["tasks"])
        if bundle.get("audit_history"):
            self.replace_audit_history(
                bundle["report"]["report_no"], bundle["audit_history"]
            )
        if bundle.get("integrated_list_row"):
            self.upsert_integrated_list_row(
                bundle["report"]["report_no"], bundle["integrated_list_row"]
            )

    def search_reports(
        self,
        *,
        order_no: str = "",
        report_no: str = "",
        project_name: str = "",
        sample_name: str = "",
        date_from: str = "",
        date_to: str = "",
        limit: int = 300,
    ) -> list[dict[str, Any]]:
        from .search import search_reports as _search

        return _search(
            self.conn,
            order_no=order_no,
            report_no=report_no,
            project_name=project_name,
            sample_name=sample_name,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

    def list_report_files(self, report_no: str) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT file_index, stored_path, original_path, original_filename
            FROM report_files
            WHERE report_no = ?
            ORDER BY file_index
            """,
            (report_no,),
        ).fetchall()
        return [dict(r) for r in rows]

    def count_project_contracts(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM project_contracts").fetchone()
        return int(row["c"]) if row else 0

    def lookup_project_contract(self, project_name: str | None) -> dict[str, Any] | None:
        """工程名称须与 Excel 中完全一致（trim 后相等）。"""
        if not project_name or not str(project_name).strip():
            return None
        key = str(project_name).strip()
        row = self.conn.execute(
            "SELECT project_name, manager, handler FROM project_contracts WHERE project_name = ?",
            (key,),
        ).fetchone()
        return dict(row) if row else None

    def replace_project_contracts(
        self, rows: list[dict[str, str]], *, source_file: str | None = None
    ) -> int:
        now = _now()
        self.conn.execute("DELETE FROM project_contracts")
        # Excel 中重复项目名称：保留最后一行
        deduped: dict[str, dict[str, str]] = {}
        for r in rows:
            name = (r.get("project_name") or "").strip()
            if name:
                deduped[name] = r
        for name, r in deduped.items():
            self.conn.execute(
                """
                INSERT INTO project_contracts (project_name, manager, handler, source_file, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    name,
                    (r.get("manager") or "").strip() or None,
                    (r.get("handler") or "").strip() or None,
                    source_file,
                    now,
                ),
            )
        self.conn.commit()
        return len(deduped)

    def import_project_contracts_from_excel(self, excel_path: str | Path) -> int:
        from .import_contracts import read_contract_rows

        rows = read_contract_rows(Path(excel_path))
        return self.replace_project_contracts(rows, source_file=str(Path(excel_path).resolve()))
