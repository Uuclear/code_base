"""RapidOCR-json CLI wrapper — https://github.com/hiroi-sora/RapidOCR-json"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# code=100 success; see project README
OCR_CODE_OK = 100


def default_rapidocr_dir() -> Path | None:
    """Resolve RapidOCR-json directory from env or common locations."""
    env = os.environ.get("RAPID_OCR_JSON") or os.environ.get("RAPIDOCR_JSON")
    if env:
        p = Path(env)
        if p.is_file():
            return p.parent
        if p.is_dir():
            return p
    # ScanReport/tools/RapidOCR-json
    candidate = Path(__file__).resolve().parents[1] / "tools" / "RapidOCR-json"
    if candidate.is_dir():
        return candidate
    return None


def _find_exe(ocr_dir: Path) -> Path:
    for name in ("RapidOCR-json.exe", "RapidOCR_json.exe", "RapidOCR-json", "RapidOCR_json"):
        p = ocr_dir / name
        if p.is_file():
            return p
    raise FileNotFoundError(f"No RapidOCR executable under {ocr_dir}")


def _parse_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError("RapidOCR produced empty stdout")
    # Last line often holds the dict
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{") and "code" in line:
            try:
                return json.loads(line.replace("'", '"'))
            except json.JSONDecodeError:
                pass
            try:
                return ast.literal_eval(line)
            except (SyntaxError, ValueError):
                pass
    m = re.search(r"\{['\"]code['\"].*\}", text, re.DOTALL)
    if m:
        blob = m.group(0)
        try:
            return ast.literal_eval(blob)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Cannot parse RapidOCR output: {blob[:200]}") from exc
    raise ValueError(f"Cannot parse RapidOCR output: {text[:300]}")


def _run_via_python_api(image_path: Path, ocr_dir: Path) -> dict[str, Any]:
    api_dir = ocr_dir / "api" / "python"
    if not (api_dir / "RapidOCR_api.py").exists():
        raise FileNotFoundError("RapidOCR_api.py not found")
    if str(api_dir) not in sys.path:
        sys.path.insert(0, str(api_dir))
    from RapidOCR_api import OcrAPI  # type: ignore[import-not-found]

    exe = _find_exe(ocr_dir)
    ocr = OcrAPI(str(exe))
    try:
        return ocr.run(str(image_path.resolve()))
    finally:
        ocr.stop()


def _run_via_cli(image_path: Path, ocr_dir: Path) -> dict[str, Any]:
    exe = _find_exe(ocr_dir)
    cmd = [str(exe), f"--image_path={image_path.resolve()}"]
    proc = subprocess.run(
        cmd,
        cwd=str(ocr_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        check=False,
    )
    if proc.returncode != 0 and not proc.stdout.strip():
        raise RuntimeError(
            f"RapidOCR exit {proc.returncode}: {proc.stderr[:500] or proc.stdout[:500]}"
        )
    return _parse_stdout(proc.stdout + "\n" + proc.stderr)


def ocr_image_to_text(image_path: Path, ocr_dir: Path | None = None) -> str:
    """
    Run RapidOCR-json on an image; return concatenated line texts (top-to-bottom).
    """
    base = ocr_dir or default_rapidocr_dir()
    if base is None:
        raise FileNotFoundError(
            "RapidOCR-json not found. Set RAPID_OCR_JSON to the extracted folder "
            "(see https://github.com/hiroi-sora/RapidOCR-json)."
        )
    base = base.resolve()
    image_path = image_path.resolve()
    if not image_path.is_file():
        raise FileNotFoundError(image_path)

    try:
        result = _run_via_python_api(image_path, base)
    except FileNotFoundError:
        result = _run_via_cli(image_path, base)

    code = int(result.get("code", -1))
    if code == OCR_CODE_OK:
        data = result.get("data") or []
        if not isinstance(data, list):
            raise ValueError(f"Unexpected OCR data: {data!r}")
        lines = [str(item.get("text", "")).strip() for item in data if item.get("text")]
        return "\n".join(lines)
    if code == 101:
        return ""
    raise RuntimeError(f"RapidOCR failed code={code} data={result.get('data')!r}")
