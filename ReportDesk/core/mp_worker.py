"""多进程批处理：子进程仅爬取+解码，主进程写库。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# 模块级单例，供 ProcessPool initializer 使用
_pipeline: Any = None
_settings: dict[str, str | None] = {}


def _init_pool(settings: dict[str, str | None]) -> None:
    global _pipeline, _settings
    _settings = settings
    from .pipeline import ReportPipeline

    ocr_dir = settings.get("rapidocr_dir")
    paddle_dir = settings.get("paddleocr_dir")
    weights = settings.get("scanreport_weights_dir")
    _pipeline = ReportPipeline(
        weights_folder=Path(weights) if weights else None,
        ocr_dir=Path(ocr_dir) if ocr_dir else None,
        paddleocr_dir=Path(paddle_dir) if paddle_dir else None,
        ocr_engine=settings.get("ocr_engine") or "auto",
        ocr_enabled=True,
    )
    if settings.get("limis_user") and settings.get("limis_base"):
        try:
            _pipeline.limis_client = _pipeline._create_limis_client(
                base_url=settings.get("limis_base"),
                username=settings.get("limis_user"),
                password=settings.get("limis_password"),
                auth_type=settings.get("limis_auth_type") or "1",
            )
            _pipeline.limis_client.login()
        except Exception:
            pass


def process_path_in_subprocess(path_str: str) -> dict[str, Any]:
    """在子进程中处理单张图片，返回可 JSON 序列化的结果摘要。"""
    global _pipeline, _settings
    if _pipeline is None:
        _init_pool(_settings)

    path = Path(path_str)
    result = _pipeline.process_image(
        path,
        limis_base=_settings.get("limis_base"),
        limis_user=_settings.get("limis_user"),
        limis_password=_settings.get("limis_password"),
        limis_auth_type=_settings.get("limis_auth_type") or "1",
    )
    return {
        "path": path_str,
        "status": result.status,
        "report_type": result.report_type,
        "report_no": result.report_no,
        "decode_method": result.decode_method,
        "error": result.error,
        "scrape_json": json.dumps(result.scrape, ensure_ascii=False) if result.scrape else None,
    }
