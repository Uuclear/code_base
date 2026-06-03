"""Association routing and JSON API helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parse_association_api import is_rptverify_success, is_signboard_success
from src.scrape_association import resolve_association_backend


def test_resolve_material():
    assert resolve_association_backend("112207186227") == "material_html"


def test_resolve_rptverify():
    assert resolve_association_backend("012345678901") == "rptverify_json"
    assert resolve_association_backend("12345678901") == "rptverify_json"


def test_resolve_signboard():
    assert resolve_association_backend("300112345678") == "signboard_json"


def test_rptverify_success_shape():
    payload = {"resultCode": 200, "data": {"reportUrl": "https://example.com/a.pdf"}}
    assert is_rptverify_success(payload)


def test_signboard_success_shape():
    payload = {"code": 200, "data": {"reportUrl": "https://example.com/b.pdf"}}
    assert is_signboard_success(payload)


if __name__ == "__main__":
    test_resolve_material()
    test_resolve_rptverify()
    test_resolve_signboard()
    test_rptverify_success_shape()
    test_signboard_success_shape()
    print("ok")
