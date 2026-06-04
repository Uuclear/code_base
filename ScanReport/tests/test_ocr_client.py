"""OCR 引擎选择与 JSON 解析。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ocr_client import _norm_engine, any_ocr_configured  # noqa: E402
from src.ocr_json_util import parse_ocr_stdout, text_from_ocr_result  # noqa: E402


class TestOcrJsonUtil(unittest.TestCase):
    def test_parse_and_text(self) -> None:
        raw = "{'code': 100, 'data': [{'text': '报告编号', 'box': [], 'score': 0.9}]}"
        result = parse_ocr_stdout(raw + "\n", label="Test")
        self.assertEqual(int(result["code"]), 100)
        text = text_from_ocr_result(result, label="Test")
        self.assertIn("报告编号", text)

    def test_empty_code(self) -> None:
        result = {"code": 101, "data": "No text"}
        self.assertEqual(text_from_ocr_result(result), "")


class TestOcrEngine(unittest.TestCase):
    def test_norm_engine(self) -> None:
        self.assertEqual(_norm_engine("paddleocr-json"), "paddleocr")
        self.assertEqual(_norm_engine("rapid"), "rapidocr")

    @patch("src.ocr_client.rapidocr_client.default_rapidocr_dir", return_value=None)
    @patch("src.ocr_client.paddleocr_client.default_paddleocr_dir", return_value=None)
    def test_any_configured_false(self, _a, _b) -> None:
        self.assertFalse(any_ocr_configured())


if __name__ == "__main__":
    unittest.main()
