"""Scrape internal LIMIS (10.1.228.22) by report number via LimisQuery client."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.qr_decode import DecodeResult

_LIMIS_QUERY_ROOT = Path(__file__).resolve().parents[2] / "LimisQuery"


def _import_limis_client():
    root = str(_LIMIS_QUERY_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from limis_client import LimisClient, LimisConfig  # type: ignore[import-not-found]

    return LimisClient, LimisConfig


def create_limis_client(
    *,
    base_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    auth_type: str | None = None,
) -> Any:
    """Create a ``LimisClient`` (caller may ``login()`` once and reuse in batch)."""
    LimisClient, LimisConfig = _import_limis_client()
    if not _LIMIS_QUERY_ROOT.is_dir():
        raise FileNotFoundError(f"LimisQuery not found at {_LIMIS_QUERY_ROOT}")

    cfg = LimisConfig(
        base_url=base_url or os.environ.get("LIMIS_BASE", "http://10.1.228.22"),
        username=username or os.environ.get("LIMIS_USER", "18321261078"),
        password=password or os.environ.get("LIMIS_PASSWORD", "liu15123311854"),
        auth_type=auth_type or os.environ.get("LIMIS_AUTH_TYPE", "1"),
    )
    return LimisClient(cfg)


def scrape_limis(
    decode: DecodeResult,
    *,
    client: Any | None = None,
    base_url: str | None = None,
    username: str | None = None,
    password: str | None = None,
    max_orders_to_scan: int = 30,
    include_detail: bool = True,
) -> dict[str, Any]:
    report_no = decode.report_no
    if not report_no:
        raise ValueError("limis scrape requires report_no on DecodeResult")

    if client is None:
        client = create_limis_client(
            base_url=base_url,
            username=username,
            password=password,
        )

    cfg = client.config
    data = client.find_exact_report(
        report_no.strip(),
        max_orders_to_scan=max_orders_to_scan,
    )

    out: dict[str, Any] = {
        "source_image": decode.image,
        "report_type": "limis",
        "identification": {
            "method": decode.decode_source,
            "report_no": report_no,
            "ocr_text_preview": decode.ocr_text_preview,
        },
        "qr_content": decode.qr_texts[0] if decode.qr_texts else "",
        "query": {
            "base_url": cfg.base_url,
            "report_no": report_no,
            "auth_type": data.get("query", {}).get("auth_type", cfg.auth_type),
        },
        "match": data.get("match"),
        "integrated_list_row": data.get("integrated_list_row"),
        "integrated_list_notes": data.get("integrated_list_notes"),
        "scan": data.get("scan"),
        "notes": data.get("notes"),
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
    if include_detail:
        out["detail"] = data.get("detail")
        out["login"] = data.get("login")
    if not (data.get("match") or {}).get("found"):
        raise ValueError(
            f"LIMIS: report {report_no!r} not found "
            f"(orders_checked={data.get('scan', {}).get('orders_checked')})"
        )
    return out
