"""QR decode with optional RapidOCR-json fallback."""

from __future__ import annotations

from pathlib import Path

from src.qr_decode import DecodeResult, decode_image
from src.rapidocr_client import default_rapidocr_dir, ocr_image_to_text
from src.text_extract import decode_from_ocr_text


def decode_image_with_fallback(
    image_path: Path,
    weights_folder: Path | None,
    *,
    ocr_enabled: bool = True,
    ocr_dir: Path | None = None,
) -> tuple[DecodeResult | None, str | None]:
    """
    Try QReader first; on no QR optionally run RapidOCR-json + regex.

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

    if default_rapidocr_dir() is None and ocr_dir is None:
        return None, "no QR code (RapidOCR-json not configured; set RAPID_OCR_JSON)"

    try:
        text = ocr_image_to_text(image_path, ocr_dir)
    except Exception as e:
        return None, f"no QR code; OCR failed: {e}"

    if not text.strip():
        return None, "no QR code; OCR found no text"

    ocr_decoded = decode_from_ocr_text(image_path, text)
    if ocr_decoded is None:
        return None, "no QR code; OCR text has no report id"

    return ocr_decoded, None
