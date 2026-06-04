"""RapidOCR-json / PaddleOCR-json 共用的 stdout JSON 解析。"""

from __future__ import annotations

import ast
import json
import re
from typing import Any

# code=100 识别到文字；101 无文字（见两项目 README）
OCR_CODE_OK = 100
OCR_CODE_EMPTY = 101


def parse_ocr_stdout(stdout: str, *, label: str = "OCR") -> dict[str, Any]:
    text = stdout.strip()
    if not text:
        raise ValueError(f"{label} produced empty stdout")
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
            raise ValueError(f"Cannot parse {label} output: {blob[:200]}") from exc
    raise ValueError(f"Cannot parse {label} output: {text[:300]}")


def text_from_ocr_result(result: dict[str, Any], *, label: str = "OCR") -> str:
    code = int(result.get("code", -1))
    if code == OCR_CODE_OK:
        data = result.get("data") or []
        if not isinstance(data, list):
            raise ValueError(f"Unexpected {label} data: {data!r}")
        lines = [str(item.get("text", "")).strip() for item in data if item.get("text")]
        return "\n".join(lines)
    if code == OCR_CODE_EMPTY:
        return ""
    raise RuntimeError(f"{label} failed code={code} data={result.get('data')!r}")
