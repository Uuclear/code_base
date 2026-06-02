"""Tests for jktac rId numDecode (handle.js). Run: python tests/test_jktac_codec.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.jktac_codec import decode_report_id, num_decode


def test_num_decode_mode2():
    assert num_decode("f6166ff", 2) == "2464422"
    assert num_decode("f6daeh2", 2) == "2487195"
    assert num_decode("ffd1hdd", 2) == "2286988"


def test_num_decode_roundtrip_mode1():
    assert num_decode("2464422", 1) == "f6166ff"


def test_decode_report_id():
    assert decode_report_id("f6166ff") == "2464422"


if __name__ == "__main__":
    test_num_decode_mode2()
    test_num_decode_roundtrip_mode1()
    test_decode_report_id()
    print("All jktac_codec tests passed.")
