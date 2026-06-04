from __future__ import annotations

from video_ocr import WatermarkPatterns, extract_watermark_fields


def test_default_patterns_basic():
    lines = [
        "user-device-001",
        "12:34:56",
        "这是一段说明",
        "dn: ABC-12",
    ]
    out = extract_watermark_fields(lines, WatermarkPatterns())
    assert out.dash_line == "user-device-001"
    assert out.time == "12:34:56"
    assert "说明" in (out.content or "")
    assert out.dn == "ABC-12"


def test_custom_time_and_dn_regex():
    lines = ["x-y", "时刻 08:09:10 结束", "dn=XYZ"]
    patterns = WatermarkPatterns(
        time=r"(?P<time>\d{2}:\d{2}:\d{2})",
        dn=r"dn\s*=\s*(?P<dnval>[A-Z]+)",
    )
    out = extract_watermark_fields(lines, patterns)
    assert out.dash_line == "x-y"
    assert out.time == "08:09:10"
    assert out.dn == "XYZ"


def test_content_named_group():
    lines = ["a-b", "00:00:01", "IGNORE", "dn: 1"]
    pat = WatermarkPatterns(
        content=r"CONTENT\s*(?P<content>.+)$",
    )
    blob_lines = ["a-b", "00:00:01", "CONTENT hello world", "dn: 1"]
    out = extract_watermark_fields(blob_lines, pat)
    assert out.content == "hello world"


def test_dash_line_regex_instead_of_hyphen_heuristic():
    lines = ["NO HYPHEN HERE", "ID_123_456", "11:22:33"]
    patterns = WatermarkPatterns(dash_line=r"(?P<d>ID_\d+_\d+)")
    out = extract_watermark_fields(lines, patterns)
    # dash_line returns full line when pattern matches via search
    assert out.dash_line == "ID_123_456"
