"""解码结果快照（dataclass，供主进程爬取时 dataclasses.replace）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ReportType = Literal["association", "institute", "limis", "unknown"]
DecodeSource = Literal["qr", "ocr", "manual"]


@dataclass
class DecodedSnapshot:
    image: str
    qr_texts: list[str]
    report_type: ReportType
    report_no: str | None = None
    anti_fake_code: str | None = None
    decode_source: DecodeSource = "qr"
    ocr_text_preview: str | None = None
