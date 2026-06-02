#!/usr/bin/env python3
"""Batch scan report images, decode QR, scrape and write JSON output."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.qr_decode import decode_image, get_qreader
from src.scrape_association import scrape_association
from src.scrape_institute import scrape_institute

ROOT = Path(__file__).resolve().parent


def process_image(
    image_path: Path,
    weights_folder: Path,
    session: requests.Session,
) -> tuple[str, dict | None, str | None]:
    """
    Returns (status, result_dict, error_message).
    status: success | skipped | failed
    """
    try:
        decoded = decode_image(image_path, weights_folder)
    except Exception as e:
        return "failed", None, f"decode error: {e}"

    if decoded is None:
        return "skipped", None, "no QR code"

    try:
        if decoded.report_type == "association":
            result = scrape_association(decoded, session)
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
    parser.add_argument("--input", "-i", type=Path, default=ROOT / "report")
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
    args = parser.parse_args()

    input_dir = args.input.resolve()
    output_dir = args.output.resolve()
    weights_folder = args.weights.resolve()

    if not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    seen: set[Path] = set()
    images: list[Path] = []
    for pattern in ("*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"):
        for p in sorted(input_dir.glob(pattern)):
            key = p.resolve()
            if key not in seen:
                seen.add(key)
                images.append(p)
    if args.limit > 0:
        images = images[: args.limit]

    if not images:
        print(f"No images in {input_dir}", file=sys.stderr)
        return 1

    print(f"Initializing QReader (weights: {weights_folder})...")
    get_qreader(weights_folder)

    session = requests.Session()
    summary = {
        "processed_at": datetime.now(timezone.utc).isoformat(),
        "input_dir": str(input_dir),
        "output_dir": str(output_dir),
        "total": len(images),
        "success": [],
        "skipped": [],
        "failed": [],
    }

    for image_path in images:
        name = image_path.name
        print(f"Processing {name}...", flush=True)
        status, result, err = process_image(image_path, weights_folder, session)

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
