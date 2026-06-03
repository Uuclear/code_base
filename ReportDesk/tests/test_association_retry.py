"""协会编号易混字符变体。"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.association_retry import all_retry_candidates, single_char_variants  # noqa: E402


class TestAssociationRetry(unittest.TestCase):
    def test_single_substitution(self) -> None:
        variants = list(single_char_variants("HNO1-123"))
        self.assertIn("HN01-123", variants)

    def test_primary_first(self) -> None:
        cands = all_retry_candidates("AB0")
        self.assertEqual(cands[0], "AB0")
        self.assertTrue(any("O" in x or "o" in x for x in cands[1:]))


if __name__ == "__main__":
    unittest.main()
