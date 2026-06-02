"""jktac handle.js numDecode — maps obfuscated rId in QR URLs to numeric report IDs."""

from __future__ import annotations

# handle.js: var arr = ['l', 'e', 'f', 'v', '6', '2', '1', 'a', 'd', 'h'];
_NUM_CHARS = ["l", "e", "f", "v", "6", "2", "1", "a", "d", "h"]


def num_decode(value: str, mode: int = 2) -> str:
    """
    Port of handle.js numDecode(str, num).
    mode 1: numeric string -> obfuscated (encode)
    mode 2: obfuscated -> numeric string (decode), used for rId
    """
    s = str(value)
    if mode == 1:
        return "".join(_NUM_CHARS[int(c)] for c in s)
    if mode == 2:
        parts: list[str] = []
        for ch in s:
            try:
                parts.append(str(_NUM_CHARS.index(ch)))
            except ValueError:
                # $.inArray returns -1 for unknown chars
                parts.append("-1")
        return "".join(parts)
    raise ValueError(f"num_decode mode must be 1 or 2, got {mode}")


def decode_report_id(rid: str) -> str:
    """Decode QR rId query param to testingReportId for GetReportInfo API."""
    decoded = num_decode(rid, 2)
    if not decoded or "-1" in decoded:
        raise ValueError(f"Invalid rId after numDecode: {rid!r} -> {decoded!r}")
    return decoded
