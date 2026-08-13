"""Automated tests for investigate_borough_gap.py (round 1 of the mechanism
hunt). Previously this script had no dedicated tests -- only the statistical
core in regression.py was covered. These exercise its own logic directly:
the structural-violation keyword match, the initial-visit violation-load
aggregation, and the initial->re-inspection gap/recurrence pairing.

All synthetic, hand-built examples -- no dependency on the real dataset.

Run with: python3 -m unittest discover -s tests -v
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from investigate_borough_gap import (  # noqa: E402
    INITIAL,
    REINSPECTION,
    compute_initial_violation_load,
    compute_reinspection_gaps,
    is_structural,
)


class TestIsStructural(unittest.TestCase):
    def test_matches_pest_language(self):
        self.assertTrue(is_structural(None, "Evidence of mice or live mice present"))
        self.assertTrue(is_structural(None, "Facility not vermin proof"))

    def test_matches_temperature_by_code_prefix(self):
        # Real DOHMH text ("Cold TCS food item held above 41 F") never
        # contains a "cold holding"/"hot holding" keyword literally -- this
        # has to be matched by the 02-family violation code, not the text.
        self.assertTrue(is_structural("02G", "Cold TCS food item held above 41 °F."))
        self.assertTrue(is_structural("02B", "Hot TCS food item not held at or above 140 °F."))

    def test_rejects_non_temperature_code_even_with_similar_wording(self):
        # Code prefix is authoritative; a non-02 code shouldn't be swept in
        # just because it happens to mention temperature-adjacent words.
        self.assertFalse(is_structural("06C", "Food not protected from potential source of contamination."))

    def test_is_case_insensitive_for_keyword_matches(self):
        self.assertTrue(is_structural(None, "EVIDENCE OF ROACHES"))

    def test_rejects_procedural_language(self):
        self.assertFalse(is_structural("04A", "Failure to post the required signage"))
        self.assertFalse(is_structural("20-08", "Permit not conspicuously displayed"))

    def test_handles_missing_code_and_description(self):
        self.assertFalse(is_structural(None, None))
        self.assertFalse(is_structural(float("nan"), float("nan")))


class TestComputeInitialViolationLoad(unittest.TestCase):
    def _row(self, camis, boro, date, code, desc, critical="Not Critical", score="10"):
        return {
            "camis": camis, "boro": boro, "inspection_date": pd.Timestamp(date),
            "inspection_type": INITIAL, "violation_code": code,
            "violation_description": desc, "critical_flag": critical, "score": score,
        }

    def test_aggregates_violations_per_visit(self):
        rows = [
            self._row("1", "Manhattan", "2023-01-01", "10F", "Non-food contact surface unclean", critical="Not Critical"),
            self._row("1", "Manhattan", "2023-01-01", "04L", "Evidence of mice", critical="Critical"),
        ]
        cycle = pd.DataFrame(rows)
        visit_load = compute_initial_violation_load(cycle)

        self.assertEqual(len(visit_load), 1)  # one visit, two violation rows
        record = visit_load.iloc[0]
        self.assertEqual(record["n_violations"], 2)
        self.assertEqual(record["n_critical"], 1)
        self.assertEqual(record["n_structural"], 1)  # only the mice citation
        self.assertTrue(record["any_structural"])
        self.assertEqual(record["score"], 10.0)

    def test_separate_visits_stay_separate(self):
        rows = [
            self._row("1", "Bronx", "2023-01-01", "10F", "unclean surface"),
            self._row("1", "Bronx", "2023-06-01", "08A", "pest harborage"),
        ]
        cycle = pd.DataFrame(rows)
        visit_load = compute_initial_violation_load(cycle)
        self.assertEqual(len(visit_load), 2)


class TestComputeReinspectionGaps(unittest.TestCase):
    def _row(self, camis, boro, itype, date, code=None, grade=None, score="10"):
        return {
            "camis": camis, "boro": boro, "inspection_type": itype,
            "inspection_date": pd.Timestamp(date), "violation_code": code, "grade": grade,
            "score": score,
        }

    def test_computes_days_between_visits(self):
        rows = [
            self._row("1", "Queens", INITIAL, "2023-01-01", code="08A"),
            self._row("1", "Queens", REINSPECTION, "2023-01-31", grade="A"),
        ]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)

        self.assertEqual(len(gap_df), 1)
        self.assertEqual(gap_df.iloc[0]["days_to_reinspect"], 30)
        self.assertFalse(gap_df.iloc[0]["b_or_c"])

    def test_detects_recurring_violation_code(self):
        rows = [
            self._row("1", "Bronx", INITIAL, "2023-01-01", code="08A"),
            self._row("1", "Bronx", REINSPECTION, "2023-02-01", code="08A", grade="B"),
        ]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)

        self.assertEqual(len(gap_df), 1)
        record = gap_df.iloc[0]
        self.assertTrue(record["any_recurring"])
        self.assertEqual(record["n_recurring_codes"], 1)
        self.assertTrue(record["b_or_c"])

    def test_new_violation_at_reinspection_is_not_recurring(self):
        rows = [
            self._row("1", "Bronx", INITIAL, "2023-01-01", code="08A"),
            self._row("1", "Bronx", REINSPECTION, "2023-02-01", code="10F", grade="A"),
        ]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)

        self.assertFalse(gap_df.iloc[0]["any_recurring"])
        self.assertEqual(gap_df.iloc[0]["n_recurring_codes"], 0)

    def test_out_of_range_gap_is_filtered_out(self):
        # 400 days apart -- outside the (0, 365] window the script uses.
        rows = [
            self._row("1", "Manhattan", INITIAL, "2020-01-01", code="08A"),
            self._row("1", "Manhattan", REINSPECTION, "2021-02-05", grade="A"),
        ]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)
        self.assertEqual(len(gap_df), 0)

    def test_reinspection_without_prior_initial_is_dropped(self):
        rows = [self._row("1", "Manhattan", REINSPECTION, "2023-01-01", grade="A")]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)
        self.assertTrue(gap_df.empty)

    def test_pairs_with_most_recent_prior_initial_not_the_first(self):
        rows = [
            self._row("1", "Queens", INITIAL, "2023-01-01", code="08A"),
            self._row("1", "Queens", INITIAL, "2023-03-01", code="04L"),  # a later initial, e.g. a new cycle
            self._row("1", "Queens", REINSPECTION, "2023-03-15", code="04L", grade="A"),
        ]
        cycle = pd.DataFrame(rows)
        gap_df = compute_reinspection_gaps(cycle)

        self.assertEqual(len(gap_df), 1)
        # Paired with the March 1 initial (14 days), not the January one (73 days).
        self.assertEqual(gap_df.iloc[0]["days_to_reinspect"], 14)
        self.assertTrue(gap_df.iloc[0]["any_recurring"])


if __name__ == "__main__":
    unittest.main()
