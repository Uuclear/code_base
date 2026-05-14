from __future__ import annotations

import re
from typing import Iterable

from video_ocr.models import WatermarkExtract, WatermarkPatterns

_DEFAULT_TIME = re.compile(
    r"(?P<time>\d{1,2}:\d{2}:\d{2}(?:[.,:]\d{1,3})?)",
)
_DEFAULT_DN = re.compile(
    r"(?P<dn>(?:dn|DN)\s*[:：]?\s*(?P<dnval>[A-Za-z0-9._-]+))",
)


def _compile(pat: str | None, default: re.Pattern[str] | None) -> re.Pattern[str] | None:
    if pat is None:
        return default
    return re.compile(pat, re.MULTILINE)


def _normalize_dn_value(raw: str) -> str:
    """Strip leading ``dn`` / ``DN`` markers with common separators."""
    s = raw.strip()
    s = re.sub(r"^(?:dn|DN)\s*[:：=]\s*", "", s, flags=re.IGNORECASE)
    return s.strip()


def _pick_dash_line(lines: list[str], pattern: re.Pattern[str] | None) -> str | None:
    if pattern is not None:
        for line in lines:
            line_st = line.strip()
            if not line_st:
                continue
            if pattern.search(line_st):
                return line_st
        return None
    for line in lines:
        line_st = line.strip()
        if "-" in line_st and line_st:
            return line_st
    return None


def _pick_time(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    if "time" in m.groupdict():
        return m.group("time")
    return m.group(0)


def _pick_dn(text: str, pattern: re.Pattern[str]) -> str | None:
    m = pattern.search(text)
    if not m:
        return None
    gd = m.groupdict()
    if "dnval" in gd and gd["dnval"]:
        return _normalize_dn_value(gd["dnval"])
    if "dn" in gd and gd["dn"]:
        return _normalize_dn_value(gd["dn"])
    return _normalize_dn_value(m.group(0))


def _pick_content(
    lines: list[str],
    patterns: WatermarkPatterns,
    content_pat: re.Pattern[str] | None,
    dash_line: str | None,
    time_value: str | None,
    dn_value: str | None,
) -> str | None:
    if content_pat is not None:
        blob = "\n".join(lines)
        m = content_pat.search(blob)
        if m and "content" in m.groupdict():
            val = m.group("content")
            return val.strip() if val else None
        if m:
            return m.group(0).strip()

    skip: set[str] = set()
    if dash_line:
        skip.add(dash_line.strip())
    if dn_value:
        for ln in lines:
            if dn_value in ln:
                skip.add(ln.strip())
    if time_value:
        for ln in lines:
            st = ln.strip()
            if not st:
                continue
            if time_value in st and len(st) <= len(time_value) + 4:
                skip.add(st)

    parts: list[str] = []
    for ln in lines:
        st = ln.strip()
        if not st or st in skip:
            continue
        parts.append(st)
    if not parts:
        return None
    return "\n".join(parts)


def extract_watermark_fields(
    ocr_lines: Iterable[str],
    patterns: WatermarkPatterns | None = None,
) -> WatermarkExtract:
    """
    Parse OCR text lines into dash_line, time, content, dn.

    * dash_line: first line containing ``-``, or first line matching ``patterns.dash_line``.
    * time: ``patterns.time`` or default ``HH:MM:SS``-style match on full text.
    * dn: ``patterns.dn`` or default ``dn:/DN:`` style token.
    * content: ``patterns.content`` with named group ``content``, or remaining lines.
    """
    patterns = patterns or WatermarkPatterns()
    lines = [ln for ln in ocr_lines if isinstance(ln, str)]

    dash_pat = _compile(patterns.dash_line, None)
    time_pat = _compile(patterns.time, _DEFAULT_TIME)
    dn_pat = _compile(patterns.dn, _DEFAULT_DN)
    content_pat = _compile(patterns.content, None)

    if time_pat is None or dn_pat is None:
        raise RuntimeError("internal: default time/dn patterns missing")

    dash_line = _pick_dash_line(lines, dash_pat)
    blob = "\n".join(lines)
    time_value = _pick_time(blob, time_pat)
    dn_value = _pick_dn(blob, dn_pat)
    content = _pick_content(lines, patterns, content_pat, dash_line, time_value, dn_value)

    return WatermarkExtract(
        dash_line=dash_line,
        time=time_value,
        content=content,
        dn=dn_value,
    )
