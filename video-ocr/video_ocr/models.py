from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WatermarkPatterns:
    """Per-field regex. Use ``None`` for built-in defaults where applicable."""

    dash_line: str | None = None
    time: str | None = None
    content: str | None = None
    dn: str | None = None


@dataclass(frozen=True)
class WatermarkExtract:
    """Structured watermark text: dash line, time, free text, dn."""

    dash_line: str | None
    time: str | None
    content: str | None
    dn: str | None
