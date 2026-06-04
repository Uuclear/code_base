"""QR decode with optional OCR fallback (RapidOCR-json / PaddleOCR-json)."""

from __future__ import annotations

from pathlib import Path

from src.ocr_client import any_ocr_configured, ocr_image_to_text
from src.qr_decode import DecodeResult, decode_image


def decode_image_with_fallback(
    image_path: Path,
    weights_folder: Path | None,
    *,
    ocr_enabled: bool = True,
    ocr_dir: Path | None = None,
    paddleocr_dir: Path | None = None,
    ocr_engine: str | None = "auto",
) -> tuple[DecodeResult | None, str | None]:
    """
    Try QReader first; on no QR optionally run OCR + regex.

    ocr_dir: RapidOCR-json 目录（兼容旧参数名）
    paddleocr_dir: PaddleOCR-json 目录
    ocr_engine: auto | rapidocr | paddleocr

    Returns (decode_result, error_message).
    """
    try:
        decoded = decode_image(image_path, weights_folder)
    except Exception as e:
        return None, f"decode error: {e}"

    if decoded is not None:
        return decoded, None

    if not ocr_enabled:
        return None, "no QR code"

    if not any_ocr_configured(ocr_dir, paddleocr_dir):
        return (
            None,
            "no QR code (OCR not configured; set RAPID_OCR_JSON or PADDLE_OCR_JSON)",
        )

    try:
        text = ocr_image_to_text(
            image_path,
            engine=ocr_engine,
            rapidocr_dir=ocr_dir,
            paddleocr_dir=paddleocr_dir,
        )
    except Exception as e:
        return None, f"no QR code; OCR failed: {e}"

    if not text.strip():
        return None, "no QR code; OCR found no text"

    from src.text_extract import decode_from_ocr_text

    ocr_decoded = decode_from_ocr_text(image_path, text)
    if ocr_decoded is None:
        return None, "no QR code; OCR text has no report id"

    return ocr_decoded, None
