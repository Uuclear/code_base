"""Test association HTML parsing."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.scrape_association import fetch_association
from src.parse_html import parse_association_html

def main():
    cases = [
        ("GC01-202604318", "112207186227"),
        ("HN01-202629448", "110807184827"),
    ]
    for report_no, code in cases:
        print(f"\n=== {report_no} ===")
        html, _ = fetch_association(report_no, code)
        parsed = parse_association_html(html)
        print(json.dumps(parsed, ensure_ascii=False, indent=2)[:3000])

if __name__ == "__main__":
    main()
