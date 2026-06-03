"""协会报告编号 OCR 易混字符：单点替换后重试爬取。"""

from __future__ import annotations

from typing import Iterator

# 每字符可替换的候选（不含自身）
_AMBIGUOUS: dict[str, str] = {
    "0": "Oo",
    "O": "0o",
    "o": "0O",
    "1": "lI",
    "l": "1I",
    "I": "1l",
    "5": "S",
    "S": "5",
    "8": "B",
    "B": "8",
    "2": "Z",
    "Z": "2",
    "6": "G",
    "G": "6",
}


def single_char_variants(report_no: str, *, max_count: int = 48) -> Iterator[str]:
    """对含易混字符的位置逐个单字符替换，生成候选编号。"""
    if not report_no:
        return
    seen: set[str] = {report_no}
    count = 0
    for i, ch in enumerate(report_no):
        alts = _AMBIGUOUS.get(ch) or _AMBIGUOUS.get(ch.upper()) or ""
        for alt in alts:
            if alt == ch:
                continue
            candidate = report_no[:i] + alt + report_no[i + 1 :]
            if candidate in seen:
                continue
            seen.add(candidate)
            yield candidate
            count += 1
            if count >= max_count:
                return


def all_retry_candidates(primary: str, *, max_count: int = 48) -> list[str]:
    """首选编号 + 单点替换变体（去重，首选在前）。"""
    out: list[str] = []
    seen: set[str] = set()
    for cand in [primary, *single_char_variants(primary, max_count=max_count)]:
        key = cand.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out
