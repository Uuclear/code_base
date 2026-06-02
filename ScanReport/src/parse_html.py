"""Shared HTML parsing utilities for report pages."""

from __future__ import annotations

from bs4 import BeautifulSoup, Tag


def _text(el: Tag | None) -> str:
    if el is None:
        return ""
    return el.get_text(strip=True)


def table_to_dict(soup: BeautifulSoup, table_id: str | None = None) -> dict[str, str]:
    """Parse a table with th/td or two-column layout into key-value dict."""
    table = soup.find(id=table_id) if table_id else None
    if table is None and table_id:
        table = soup.find("table", id=table_id)
    if table is None:
        return {}

    result: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            key = _text(cells[0]).rstrip("：:")
            val = _text(cells[1])
            if key:
                result[key] = val
        elif len(cells) == 1:
            continue
    return result


def parse_association_html(html: str) -> dict:
    """Parse SCETIA association report HTML."""
    soup = BeautifulSoup(html, "lxml")
    project = table_to_dict(soup, "generalProjectAndConsignInfo")

    # Normalize common field names
    project_normalized = {
        "consign_no": project.get("委托编号") or project.get("委托号"),
        "project_name": project.get("工程名称") or project.get("项目名称"),
        "report_no": project.get("报告编号"),
        "consign_date": project.get("委托日期"),
        "report_date": project.get("报告日期"),
        **{k: v for k, v in project.items() if k not in ("委托编号", "工程名称", "报告编号", "委托日期", "报告日期")},
    }

    samples: list[dict] = []
    for table in soup.find_all("table"):
        title = table.get("title") or ""
        if title.endswith("_generalSampleInfo") or "样品" in _text(table.find("caption")):
            headers: list[str] = []
            for row in table.find_all("tr"):
                cells = row.find_all(["th", "td"])
                if not cells:
                    continue
                if row.find("th") and not samples:
                    headers = [_text(c) for c in cells]
                    continue
                if headers and len(cells) >= 2:
                    row_data = {}
                    for i, c in enumerate(cells):
                        key = headers[i] if i < len(headers) else f"col_{i}"
                        if key:
                            row_data[key] = _text(c)
                    if any(row_data.values()):
                        samples.append(row_data)

    if not samples:
        # Fallback: any data rows in sample-like tables
        for table in soup.select("table.sample, table[id*='Sample']"):
            for row in table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    samples.append({"raw": [_text(c) for c in cells]})

    return {
        "project": {k: v for k, v in project_normalized.items() if v},
        "samples": samples,
        "raw_tables": project,
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
