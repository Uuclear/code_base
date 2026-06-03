"""
Report / consign / anti-fake number patterns (business rules).

- 内网 LIMIS 与 院网 jktac：同一套「报告编号」——字母前缀 + '-' + 数字后缀（后缀通常 ≥6 位）。
- 协会：报告编号为 4~10 位数字（可为 ``GC01-202604318`` 形式，后缀 4~10 位；或纯数字）。
- 委托编号（协会表单等）：纯数字 4~6 位，不得当作防伪码。
- 防伪校验码（OCR）：仅「防伪校验码」标签后的 **10 位或 12 位**纯数字。
- 二维码：``报告编号|10或12位防伪码``（无标签，来自扫码）。
"""

from __future__ import annotations

import re

# 内网 / 院网 报告编号（同一规则）
LIMIS_INSTITUTE_REPORT_NO = re.compile(
    r"([A-Z]{2,4}\d{0,4}[A-Z]?-\d{6,})",
    re.IGNORECASE,
)

# 协会：带字母前缀的报告编号（连字符后 4~10 位数字）
ASSOCIATION_REPORT_ALNUM = re.compile(
    r"([A-Z]{2,4}\d{0,4}[A-Z]?-\d{4,10})\b",
    re.IGNORECASE,
)

# 协会：纯数字报告编号 4~10 位（需结合标签或 pipe 使用，避免误匹配）
ASSOCIATION_REPORT_NUMERIC = re.compile(r"\b(\d{4,10})\b")

# 二维码 / 扫码内容：编号|防伪码（防伪为 10 或 12 位，非 OCR 标签路径）
PIPE_ASSOCIATION_PATTERN = re.compile(
    r"([A-Z]{2,4}\d{0,4}[A-Z]?-\d{4,10}|\d{4,10})\s*[|｜]\s*(\d{10}|\d{12})\b",
    re.IGNORECASE,
)

# 委托编号：纯数字 4~6 位（协会表单）
CONSIGN_NO_NUMERIC = re.compile(
    r"委托编号[：:\s]*(\d{4,6})\b",
    re.IGNORECASE,
)

CONSIGN_NO_LABELED = re.compile(
    r"委托编号[：:\s]*(\d{4,12})\b",
    re.IGNORECASE,
)

LIMIS_ORDER_NO = re.compile(
    r"委托编号[：:\s]*([A-Z]{2,4}\d{0,4}[A-Z]?-\d{6,})",
    re.IGNORECASE,
)

LABEL_REPORT_NO = re.compile(
    r"报告编号[：:\s]*"
    r"([A-Z]{2,4}\d{0,4}[A-Z]?-\d{6,}"
    r"|\d{4,10})",
    re.IGNORECASE,
)

# OCR / 正文：仅认「防伪校验码」标签后的 10 或 12 位数字
LABEL_ANTI_FAKE = re.compile(
    r"防伪校验码[：:\s]*(\d{10}|\d{12})\b",
    re.IGNORECASE,
)

REPORT_NO_PATTERN = LIMIS_INSTITUTE_REPORT_NO


def excluded_from_anti_fake(text: str) -> set[str]:
    """Digit strings that must not be chosen as 防伪码."""
    out: set[str] = set()
    for pat in (CONSIGN_NO_LABELED, CONSIGN_NO_NUMERIC):
        for m in pat.finditer(text):
            out.add(m.group(1))
    return out


def is_valid_anti_fake(code: str, excluded: set[str] | None = None) -> bool:
    if excluded and code in excluded:
        return False
    return code.isdigit() and len(code) in (10, 12)


def find_anti_fake_code(text: str) -> str | None:
    """OCR/正文：仅从「防伪校验码」标签后取 10 或 12 位数字。"""
    m = LABEL_ANTI_FAKE.search(text)
    if not m:
        return None
    code = m.group(1)
    if is_valid_anti_fake(code, excluded_from_anti_fake(text)):
        return code
    return None


def find_association_report_no(text: str, *, allow_pipe: bool = True) -> str | None:
    if allow_pipe:
        m = PIPE_ASSOCIATION_PATTERN.search(text)
        if m:
            rn = m.group(1)
            return rn.upper() if rn[0].isalpha() else rn
    m = LABEL_REPORT_NO.search(text)
    if m:
        val = m.group(1)
        return val.upper() if val[0].isalpha() else val
    m = ASSOCIATION_REPORT_ALNUM.search(text)
    if m:
        return m.group(1).upper()
    return None


def find_limis_institute_report_no(text: str) -> str | None:
    m = LABEL_REPORT_NO.search(text)
    if m and m.group(1)[0].isalpha():
        return m.group(1).upper()
    m = LIMIS_INSTITUTE_REPORT_NO.search(text)
    if m:
        return m.group(1).upper()
    return None
