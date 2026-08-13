"""Tests for supabase/load_data.py's clean_row().

clean_row() is the one piece of real logic in the Supabase loader -- it
selects the columns that matter, drops the NYC feed's internal geo-join
fields, and coerces score to an int or None. Everything else in that script
is I/O (reading the JSON extract, talking to Supabase), which these tests
don't touch -- no network, no credentials needed. This is why load_data.py
imports dotenv/supabase lazily inside main() rather than at module load:
so this file can import clean_row without supabase/requirements.txt being
installed.

Run with: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "supabase"))

from load_data import COLUMNS, clean_row  # noqa: E402


class TestCleanRow(unittest.TestCase):
    def test_keeps_only_the_expected_columns(self):
        raw = {"camis": "123", "dba": "TEST DELI", "unexpected_field": "should be dropped"}
        cleaned = clean_row(raw)
        self.assertEqual(set(cleaned.keys()), set(COLUMNS))
        self.assertNotIn("unexpected_field", cleaned)

    def test_drops_computed_region_columns(self):
        raw = {"camis": "123", ":@computed_region_f5dn_yrer": "17", ":@computed_region_yeji_bk3q": "2"}
        cleaned = clean_row(raw)
        self.assertNotIn(":@computed_region_f5dn_yrer", cleaned)
        self.assertNotIn(":@computed_region_yeji_bk3q", cleaned)

    def test_fills_missing_columns_with_none(self):
        cleaned = clean_row({"camis": "123"})
        self.assertIsNone(cleaned["dba"])
        self.assertIsNone(cleaned["grade"])

    def test_coerces_score_string_to_int(self):
        self.assertEqual(clean_row({"score": "25"})["score"], 25)

    def test_coerces_score_float_string_to_int(self):
        # The raw NYC feed sometimes has scores like "25.0".
        self.assertEqual(clean_row({"score": "25.0"})["score"], 25)

    def test_missing_score_becomes_none(self):
        self.assertIsNone(clean_row({})["score"])

    def test_empty_string_score_becomes_none(self):
        self.assertIsNone(clean_row({"score": ""})["score"])

    def test_unparseable_score_becomes_none_not_a_crash(self):
        # Real-world data quality issue this guards against: a stray
        # non-numeric score shouldn't take down the whole load.
        self.assertIsNone(clean_row({"score": "N/A"})["score"])

    def test_none_score_stays_none(self):
        self.assertIsNone(clean_row({"score": None})["score"])


if __name__ == "__main__":
    unittest.main()
