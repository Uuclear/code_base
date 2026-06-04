#!/usr/bin/env python3
"""Batch scan report images, decode QR, scrape and write JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from src.decode_pipeline import decode_image_with_fallback
from src.qr_decode import get_qreader
from src.scrape_association import scrape_association
from src.scrape_institute import scrape_institute
from src.scrape_limis import create_limis_client, scrape_limis

ROOT = Path(__file__).resolve().parent

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
GLOB_PATTERNS = ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG")


def collect_images(inputs: list[Path]) -> tuple[list[Path], list[str]]:
    """
    Resolve -i paths: each may be a single image file or a directory of images.
    Returns (images, errors for missing paths).
    """
    seen: set[Path] = set()
    images: list[Path] = []
    errors: list[str] = []

    for raw in inputs:
        path = raw.resolve()
        if path.is_file():
            if path.suffix.lower() not in IMAGE_SUFFIXES:
                errors.append(f"not an image file: {path}")
                continue
            key = path.resolve()
            if key not in seen:
                seen.add(key)
                images.append(path)
        elif path.is_dir():
            for pattern in GLOB_PATTERNS:
                for p in sorted(path.glob(pattern)):
                    key = p.resolve()
                    if key not in seen:
                        seen.add(key)
                        images.append(p)
        else:
            errors.append(f"not found: {path}")

    images.sort(key=lambda p: p.name.lower())
    return images, errors


def process_image(
    image_path: Path,
    weights_folder: Path,
    session: requests.Session,
    limis_ctx: dict[str, Any],
    *,
    ocr_enabled: bool = True,
    ocr_dir: Path | None = None,
    paddleocr_dir: Path | None = None,
    ocr_engine: str | None = "auto",
    limis_include_detail: bool = True,
) -> tuple[str, dict | None, str | None]:
    """
    Returns (status, result_dict, error_message).
    status: success | skipped | failed
    """
    decoded, err = decode_image_with_fallback(
        image_path,
        weights_folder,
        ocr_enabled=ocr_enabled,
        ocr_dir=ocr_dir,
        paddleocr_dir=paddleocr_dir,
        ocr_engine=ocr_engine,
    )
    if decoded is None:
        return "skipped", None, err or "no QR code"

    try:
        if decoded.report_type == "association":
            result = scrape_association(decoded, session)
        elif decoded.report_type == "limis":
            if limis_ctx.get("client") is None:
                limis_ctx["client"] = create_limis_client()
                print("LIMIS: logging in (reuse session for batch)...", flush=True)
                limis_ctx["client"].login()
                limis_ctx["logins"] = 1
            result = scrape_limis(
                decoded,
                client=limis_ctx["client"],
                include_detail=limis_include_detail,
            )
        elif decoded.report_type == "institute":
            result = scrape_institute(decoded, session)
        else:
            # Try institute if any http URL present
            if any(
                t.strip().lower().startswith(("http://", "https://"))
                for t in decoded.qr_texts
            ):
                result = scrape_institute(decoded, session)
            else:
                return (
                    "failed",
                    None,
                    f"unknown report type, qr={decoded.qr_texts}",
                )
        return "success", result, None
    except Exception as e:
        return "failed", None, str(e)


def main() -> int:
    parser = argparse.ArgumentParser(description="ScanReport QR pipeline")
    parser.add_argument(
        "--input",
        "-i",
        action="append",
        type=Path,
        metavar="PATH",
        help="Report image file or directory (repeatable). Default: ./report",
    )
    parser.add_argument("--output", "-o", type=Path, default=ROOT / "output")
    parser.add_argument(
        "--weights",
        type=Path,
        default=ROOT,
        help="Folder containing qrdet-*.pt weights",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max images to process (0 = all)",
    )
    parser.add_argument(
        "--no-ocr",
        action="store_true",
        help="Disable OCR fallback when QR is missing",
    )
    parser.add_argument(
        "--rapidocr",
        type=Path,
        default=None,
        help="Path to RapidOCR-json folder (or set RAPID_OCR_JSON)",
    )
    parser.add_argument(
        "--paddleocr",
        type=Path,
        default=None,
        help="Path to PaddleOCR-json folder (or set PADDLE_OCR_JSON)",
    )
    parser.add_argument(
        "--ocr-engine",
        choices=("auto", "rapidocr", "paddleocr"),
        default="auto",
        help="OCR engine when QR missing (default: auto)",
    )
    parser.add_argument(
        "--limis-slim",
        action="store_true",
        help="LIMIS OCR path: only match metadata, skip detail bundle",
    )
    args = parser.parse_args()

    input_paths = args.input if args.input else [ROOT / "report"]
    output_dir = args.output.resolve()
    weights_folder = args.weights.resolve()

    images, input_errors = collect_images(input_paths)
    for msg in input_errors:
        print(msg, file=sys.stderr)
    if input_errors and not images:
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    if args.limit > 0:
        images = images[: args.limit]

    if not images:
        print(
            f"No images under: {', '.join(str(p) for p in input_paths)}",
            file=sys.stderr,
        )
        return 1

    print(f"Initializing QReader (weights: {weights_folder})...")
    get_qreader(weights_folder)

    session = requests.Session()
    limis_ctx: dict[str, Any] = {"client": None, "logins": 0}
    summary = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "input": [str(p.resolve()) for p in input_paths],
        "output_dir": str(output_dir),
        "total": len(images),
        "limis_session_logins": 0,
        "success": [],
        "skipped": [],
        "failed": [],
    }

    for image_path in images:
        name = image_path.name
        print(f"Processing {name}...", flush=True)
        status, result, err = process_image(
            image_path,
            weights_folder,
            session,
            limis_ctx,
            ocr_enabled=not args.no_ocr,
            ocr_dir=args.rapidocr,
            paddleocr_dir=args.paddleocr,
            ocr_engine=args.ocr_engine,
            limis_include_detail=not args.limis_slim,
        )

        if status == "success" and result:
            out_file = output_dir / f"{image_path.stem}.json"
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            summary["success"].append({"image": name, "output": out_file.name})
            print(f"  OK -> {out_file.name}")
        elif status == "skipped":
            summary["skipped"].append({"image": name, "reason": err or "skipped"})
            print(f"  SKIP: {err}")
        else:
            summary["failed"].append({"image": name, "error": err or "unknown"})
            print(f"  FAIL: {err}")

    summary["limis_session_logins"] = limis_ctx.get("logins", 0)

    summary_path = output_dir / "summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(
        f"\nDone: {len(summary['success'])} success, "
        f"{len(summary['skipped'])} skipped, "
        f"{len(summary['failed'])} failed"
    )
    print(f"Summary: {summary_path}")
    return 0 if not summary["failed"] else 1


if __name__ == "__main__":
    sys.exit(main())
