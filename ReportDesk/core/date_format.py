"""报告日期解析与统一展示为 YYYY-MM-DD。"""

from __future__ import annotations

import re

_DATE_FULL = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")
_DATE_YM = re.compile(r"(\d{4})\D+(\d{1,2})\b")


def parse_report_date_key(value: str | None) -> int | None:
    """解析为 yyyymmdd 整数，用于排序与区间比较。"""
    if not value:
        return None
    s = str(value).strip()
    m = _DATE_FULL.search(s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            return y * 10000 + mo * 100 + d
    m2 = _DATE_YM.search(s)
    if m2:
        y, mo = int(m2.group(1)), int(m2.group(2))
        if 1 <= mo <= 12:
            return y * 10000 + mo * 100 + 1
    return None


def format_report_date(value: str | None) -> str:
    """统一显示/存储用日期：YYYY-MM-DD；无法解析则返回去空白原文。"""
    key = parse_report_date_key(value)
    if key is None:
        return str(value).strip() if value else ""
    y = key // 10000
    m = (key % 10000) // 100
    d = key % 100
    return f"{y:04d}-{m:02d}-{d:02d}"
