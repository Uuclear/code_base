"""Shared HTML parsing utilities for report pages."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup, NavigableString, Tag

# Sample table cell id suffix -> normalized key (ReportDHTML.js: title *_generalSampleInfo)
_SAMPLE_FIELD_MAP = {
    "sample_ID": "sample_no",
    "sampleName": "sample_name",
    "delegate_Quan": "delegate_quantity",
    "produce_Factory": "manufacturer",
    "specName": "specification",
    "gradeName": "grade",
    "proJect_Part": "project_part",
    "exam_Result": "exam_result",
    "molding_Date": "molding_date",
    "ageTime": "age_time",
    "jcrq": "testing_date",
}

# Chinese label in row -> normalized project key
_PROJECT_LABEL_MAP = {
    "委托编号": "consign_no",
    "委托号": "consign_no",
    "报告编号": "report_no",
    "委托日期": "consign_date",
    "报告日期": "report_date",
    "工程名称": "project_name",
    "项目名称": "project_name",
    "委托性质": "consign_type",
    "工程连续号": "project_serial_no",
    "委托单位": "unit_name",
    "工程地址": "project_address",
    "标段": "project_section",
    "工程附加名称": "project_section_extra",
    "施工单位": "construction_unit",
    "见证单位": "witness_unit",
    "取样人及证书号": "sampler",
    "见证人及证书号": "witness",
    "全称": "institute_name",
    "地址": "institute_address",
    "电话": "institute_phone",
    "邮编": "institute_postcode",
    "防伪校验码": "anti_fake_code",
}


def _text(el: Tag | None) -> str:
    if el is None:
        return ""
    return el.get_text(strip=True)


def _parse_key_value(text: str) -> tuple[str | None, str | None]:
    text = text.strip()
    if not text:
        return None, None
    for sep in ("：", ":"):
        if sep in text:
            key, _, val = text.partition(sep)
            return key.strip(), val.strip()
    return None, text


def _normalize_key(key: str) -> str:
    key = key.strip().rstrip("：:")
    return _PROJECT_LABEL_MAP.get(key, key)


def _text_before_element(el: Tag) -> str:
    parts: list[str] = []
    for sib in el.previous_siblings:
        if isinstance(sib, NavigableString):
            parts.append(str(sib))
    return "".join(parts).strip()


def _fields_from_cell(cell: Tag) -> dict[str, str]:
    """Extract key-value pairs from a table cell (supports span layout from SCETIA)."""
    result: dict[str, str] = {}
    pending_key: str | None = None

    for child in cell.children:
        if isinstance(child, NavigableString):
            chunk = str(child).strip()
            if not chunk:
                continue
            key, val = _parse_key_value(chunk)
            if key and val:
                nk = _normalize_key(key)
                result[nk if nk != key else key] = val
                pending_key = None
            elif key and not val:
                pending_key = key
            elif pending_key and chunk:
                nk = _normalize_key(pending_key)
                result[nk if nk != pending_key else pending_key] = chunk
                pending_key = None
        elif getattr(child, "name", None) == "span":
            st = _text(child)
            if pending_key:
                nk = _normalize_key(pending_key)
                result[nk if nk != pending_key else pending_key] = st
                pending_key = None
            else:
                k, v = _parse_key_value(st)
                if k and v is not None:
                    nk = _normalize_key(k)
                    result[nk if nk != k else k] = v

    if not result:
        key, val = _parse_key_value(_text(cell))
        if key and val:
            nk = _normalize_key(key)
            result[nk if nk != key else key] = val
    return result


def _parse_row_cells(cells: list[Tag]) -> dict[str, str]:
    result: dict[str, str] = {}
    if not cells:
        return result

    if len(cells) == 1:
        result.update(_fields_from_cell(cells[0]))
        return result

    if len(cells) == 2:
        c0, c1 = cells[0], cells[1]
        k0 = _text(c0).rstrip("：:")
        v1 = _text(c1)
        # Label + free-text value (e.g. 工程地址 with 东至/西至 inside)
        if k0 and v1 and "：" not in k0 and ":" not in k0:
            nk = _normalize_key(k0)
            if nk in _PROJECT_LABEL_MAP.values() or k0 in _PROJECT_LABEL_MAP:
                result[nk] = v1
                return result
        f0 = _fields_from_cell(c0)
        f1 = _fields_from_cell(c1)
        if f0:
            result.update(f0)
        if f1:
            result.update(f1)
        if not f0 and not f1 and k0 and v1:
            nk = _normalize_key(k0)
            result[nk if nk != k0 else k0] = v1
        return result

    if len(cells) >= 4:
        for i in range(0, len(cells) - 1, 2):
            k_cell, v_cell = cells[i], cells[i + 1]
            fk = _fields_from_cell(k_cell)
            fv = _fields_from_cell(v_cell)
            if fk:
                result.update(fk)
            elif fv:
                result.update(fv)
            else:
                key = _text(k_cell).rstrip("：:")
                val = _text(v_cell)
                if key and val:
                    nk = _normalize_key(key)
                    result[nk if nk != key else key] = val
    return result


def _parse_report_conclusions(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse multi-sample conclusion lines from report conclusion row or links."""
    items: list[dict[str, str]] = []
    for a in soup.find_all("a", title=lambda t: t and "hrefToSampleDetail" in t):
        sample_id = (a.get("href") or "").strip().lstrip("#")
        conclusion = _text(a)
        conclusion = re.sub(r"^结论[:：]\s*", "", conclusion)
        if sample_id:
            items.append({"sample_no": sample_id, "conclusion": conclusion})

    if items:
        return items

    for row in soup.select("#generalProjectAndConsignInfo tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue
        label = _text(cells[0])
        if "报告结论" not in label and "结论" not in label:
            continue
        body = _text(cells[-1])
        for m in re.finditer(
            r"样品编号[:：]\s*(\d+)\s*结论[:：]\s*([^样]+?)(?=样品编号|$)",
            body,
        ):
            items.append(
                {"sample_no": m.group(1).strip(), "conclusion": m.group(2).strip()}
            )
        if not items and body:
            items.append({"raw": body})
    return items


def table_to_dict(soup: BeautifulSoup, table_id: str | None = None) -> dict[str, str]:
    table = soup.find(id=table_id) if table_id else None
    if table is None and table_id:
        table = soup.find("table", id=table_id)
    if table is None:
        return {}

    result: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if not cells:
            continue
        label = _text(cells[0])
        if "报告结论" in label:
            continue
        row_fields = _parse_row_cells(cells)
        result.update(row_fields)
    return result


def _parse_sample_tables(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Parse hidden sample tables (title ends with _generalSampleInfo per ReportDHTML.js)."""
    samples: list[dict[str, str]] = []
    for table in soup.find_all("table"):
        title = table.get("title") or ""
        if not title.endswith("_generalSampleInfo"):
            continue
        prefix = title.replace("_generalSampleInfo", "").lstrip("_")
        sample: dict[str, str] = {}
        if prefix:
            sample["sample_table_id"] = prefix

        id_prefix = f"_{prefix}_" if prefix else "_"
        for el in table.find_all(["td", "span"], id=True):
            tid = el.get("id") or ""
            if prefix and not tid.startswith(id_prefix):
                continue
            suffix = tid[len(id_prefix) :] if prefix else tid.lstrip("_")
            norm = _SAMPLE_FIELD_MAP.get(suffix, suffix)
            if norm not in sample or _text(el):
                sample[norm] = _text(el)

        if any(v for k, v in sample.items() if k != "sample_table_id"):
            samples.append(sample)
    return samples


def _normalize_project(raw: dict[str, str]) -> dict[str, str]:
    """Build project dict with canonical keys plus remaining Chinese fields."""
    out: dict[str, str] = {}
    used_raw_keys: set[str] = set()

    canonical_sources = {
        "consign_no": ("consign_no", "委托编号", "委托号"),
        "report_no": ("report_no", "报告编号"),
        "project_name": ("project_name", "工程名称", "项目名称"),
        "consign_date": ("consign_date", "委托日期"),
        "report_date": ("report_date", "报告日期"),
        "consign_type": ("consign_type", "委托性质"),
        "project_serial_no": ("project_serial_no", "工程连续号"),
        "unit_name": ("unit_name", "委托单位"),
        "project_address": ("project_address", "工程地址"),
        "project_section": ("project_section", "标段"),
        "construction_unit": ("construction_unit", "施工单位"),
        "witness_unit": ("witness_unit", "见证单位"),
        "sampler": ("sampler", "取样人及证书号"),
        "witness": ("witness", "见证人及证书号"),
        "institute_name": ("institute_name", "全称", "检测机构信息"),
        "institute_address": ("institute_address", "地址"),
        "institute_phone": ("institute_phone", "电话"),
        "institute_postcode": ("institute_postcode", "邮编"),
        "anti_fake_code": ("anti_fake_code", "防伪校验码"),
    }

    for out_key, sources in canonical_sources.items():
        for sk in sources:
            if sk in raw and raw[sk]:
                out[out_key] = raw[sk]
                used_raw_keys.add(sk)
                break

    skip = used_raw_keys | {
        "委托编号",
        "工程名称",
        "报告编号",
        "委托日期",
        "报告日期",
        "工程信息",
    }
    for k, v in raw.items():
        if k not in skip and v:
            out[k] = v
    return {k: v for k, v in out.items() if v}


def parse_association_html(html: str) -> dict:
    """Parse SCETIA association report HTML."""
    soup = BeautifulSoup(html, "lxml")
    raw_project = table_to_dict(soup, "generalProjectAndConsignInfo")
    project = _normalize_project(raw_project)
    samples = _parse_sample_tables(soup)
    conclusions = _parse_report_conclusions(soup)

    if conclusions:
        project["report_conclusions"] = conclusions

    # Drop stray keys from mis-parsed conclusion rows
    for stray in ("样品编号", "结论"):
        raw_project.pop(stray, None)
        project.pop(stray, None)

    return {
        "project": project,
        "samples": samples,
        "raw_tables": raw_project,
    }


def parse_institute_html(html: str, url: str) -> dict:
    """Parse institute (院网) report page — generic table extraction."""
    soup = BeautifulSoup(html, "lxml")
    fields: dict[str, str] = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["th", "td"])
            if len(cells) >= 2:
                key = _text(cells[0]).rstrip("：:")
                val = _text(cells[1])
                if key and val:
                    fields[key] = val

    title = ""
    if soup.title:
        title = soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        title = title or h1.get_text(strip=True)

    return {
        "title": title,
        "source_url": url,
        "fields": fields,
    }
