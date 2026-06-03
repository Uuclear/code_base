"""Tests for OCR text classification (no RapidOCR binary required)."""

from __future__ import annotations

from pathlib import Path

from src.text_extract import classify_from_ocr_text, decode_from_ocr_text


def test_ocr_association_requires_antifake_label():
    """OCR 无「防伪校验码」标签时，pipe 形文本不得带出防伪码。"""
    t, rn, af = classify_from_ocr_text("LX3S-202600055|120707188344")
    assert af is None


def test_ocr_association_labeled_antifake():
    t, rn, af = classify_from_ocr_text(
        "报告编号：LX3S-202600055\n防伪校验码：120707188344"
    )
    assert t == "association"
    assert rn == "LX3S-202600055"
    assert af == "120707188344"


def test_ocr_rejects_11_digit_antifake_label():
    t, rn, af = classify_from_ocr_text(
        "报告编号：LX3S-202600055\n防伪校验码：12070718834"
    )
    assert af is None


def test_ocr_ignores_bare_12_digit_without_label():
    text = "报告编号：GC01-202604318\n112207186227\n"
    t, rn, af = classify_from_ocr_text(text)
    assert af is None


def test_limis_report_only():
    t, rn, af = classify_from_ocr_text(
        "上海建科检验有限公司\n报告编号 JG018-250187\n委托单位 测试"
    )
    assert t == "limis"
    assert rn == "JG018-250187"
    assert af is None


def test_limis_cover_labels_not_order_no():
    text = (
        "委托编号：JG01-250190\n"
        "报告编号：JG018-250187\n"
        "委托单位：上海机场（集团）有限公司"
    )
    t, rn, af = classify_from_ocr_text(text)
    assert t == "limis"
    assert rn == "JG018-250187"
    assert af is None


def test_institute_url_in_ocr():
    t, rn, af = classify_from_ocr_text(
        "扫码验证 https://zy.jktac.com/WeChat/rQuery?rId=abc&rNo=FS188-250078"
    )
    assert t == "institute"
    assert rn is None


def test_decode_from_ocr_text():
    d = decode_from_ocr_text(
        Path("cover.jpg"),
        "CC018-260001 检验检测报告",
    )
    assert d is not None
    assert d.decode_source == "ocr"
    assert d.report_type == "limis"
    assert d.report_no == "CC018-260001"


def test_association_ocr_excludes_consign_no():
    text = (
        "委托编号：2026055212\n"
        "报告编号：GC01-202604318\n"
        "防伪校验码：112207186227\n"
    )
    t, rn, af = classify_from_ocr_text(text)
    assert t == "association"
    assert rn == "GC01-202604318"
    assert af == "112207186227"
    assert af != "2026055212"


def test_association_numeric_report_label():
    t, rn, af = classify_from_ocr_text("报告编号：260055\n防伪校验码：120707188344")
    assert t == "association"
    assert rn == "260055"
    assert af == "120707188344"


if __name__ == "__main__":
    test_ocr_association_requires_antifake_label()
    test_ocr_association_labeled_antifake()
    test_ocr_rejects_11_digit_antifake_label()
    test_ocr_ignores_bare_12_digit_without_label()
    test_limis_report_only()
    test_limis_cover_labels_not_order_no()
    test_institute_url_in_ocr()
    test_decode_from_ocr_text()
    test_association_ocr_excludes_consign_no()
    test_association_numeric_report_label()
    print("all passed")
