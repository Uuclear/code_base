"""DecodedSnapshot 与 pipeline.replace 兼容。"""

from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.decoded_snapshot import DecodedSnapshot  # noqa: E402
from core.decode_worker import dict_to_decode_outcome  # noqa: E402


class TestDecodedSnapshot(unittest.TestCase):
    def test_replace_for_scrape(self) -> None:
        d = DecodedSnapshot(
            image="a.jpg",
            qr_texts=["LX3S-1|123"],
            report_type="association",
            report_no="LX3S-1",
            anti_fake_code="123",
        )
        d2 = replace(d, report_no="LX3S-2")
        self.assertEqual(d2.report_no, "LX3S-2")

    def test_dict_roundtrip(self) -> None:
        data = {
            "status": "success",
            "source_image": "b.jpg",
            "report_type": "limis",
            "report_no": "JG001",
            "anti_fake_code": None,
            "decode_method": "qr",
            "qr_text": "x",
            "ocr_preview": None,
            "error": None,
            "qr_texts": ["x"],
            "has_decoded": True,
        }
        o = dict_to_decode_outcome(data)
        self.assertIsNotNone(o.decoded)
        d3 = replace(o.decoded, report_no="JG002")
        self.assertEqual(d3.report_no, "JG002")


if __name__ == "__main__":
    unittest.main()
