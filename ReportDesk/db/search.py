"""报告库模糊查询与日期区间过滤。"""

from __future__ import annotations

import sqlite3
from typing import Any

from core.date_format import format_report_date, parse_report_date_key


def _date_in_range(
    report_date: str | None,
    date_from: str | None,
    date_to: str | None,
) -> bool:
    rd = parse_report_date_key(report_date)
    df = parse_report_date_key(date_from) if date_from else None
    dt = parse_report_date_key(date_to) if date_to else None
    if df is None and dt is None:
        return True
    if rd is None:
        return False
    if df is not None and rd < df:
        return False
    if dt is not None and rd > dt:
        return False
    return True


def search_reports(
    conn: sqlite3.Connection,
    *,
    order_no: str = "",
    report_no: str = "",
    project_name: str = "",
    sample_name: str = "",
    date_from: str = "",
    date_to: str = "",
    limit: int = 300,
) -> list[dict[str, Any]]:
    """模糊查询 reports + samples + tasks，日期区间在 Python 侧过滤。"""
    clauses = ["1=1"]
    params: list[Any] = []

    if order_no.strip():
        p = f"%{order_no.strip()}%"
        clauses.append("(r.order_no LIKE ? OR CAST(r.testing_order_id AS TEXT) LIKE ?)")
        params.extend([p, p])

    if report_no.strip():
        p = f"%{report_no.strip().upper()}%"
        clauses.append("r.report_no LIKE ?")
        params.append(p)

    if project_name.strip():
        p = f"%{project_name.strip()}%"
        clauses.append("r.project_name LIKE ?")
        params.append(p)

    if sample_name.strip():
        p = f"%{sample_name.strip()}%"
        clauses.append(
            """(
                EXISTS (
                    SELECT 1 FROM report_samples s
                    WHERE s.report_no = r.report_no AND s.sample_name LIKE ?
                )
                OR EXISTS (
                    SELECT 1 FROM report_tasks t
                    WHERE t.report_no = r.report_no AND t.sample_name LIKE ?
                )
            )"""
        )
        params.extend([p, p])

    where = " AND ".join(clauses)
    sql = f"""
        SELECT
            r.report_no,
            r.order_no,
            r.project_name,
            r.report_date,
            r.source_channel,
            r.scrape_status,
            (
                SELECT GROUP_CONCAT(DISTINCT x.sn)
                FROM (
                    SELECT sample_name AS sn FROM report_samples
                    WHERE report_no = r.report_no AND sample_name IS NOT NULL
                    UNION
                    SELECT sample_name AS sn FROM report_tasks
                    WHERE report_no = r.report_no AND sample_name IS NOT NULL
                ) x
            ) AS sample_names,
            (
                SELECT stored_path FROM report_files f
                WHERE f.report_no = r.report_no
                ORDER BY f.file_index LIMIT 1
            ) AS preview_path
        FROM reports r
        WHERE {where}
        ORDER BY r.updated_at DESC
        LIMIT ?
    """
    params.append(limit * 3)
    rows = conn.execute(sql, params).fetchall()

    out: list[dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        if not _date_in_range(d.get("report_date"), date_from, date_to):
            continue
        d["report_date"] = format_report_date(d.get("report_date"))
        d["report_date_key"] = parse_report_date_key(d.get("report_date"))
        out.append(d)
        if len(out) >= limit:
            break
    return out
