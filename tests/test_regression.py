"""Automated tests for regression.py and the analysis pipeline built on it.

Run with:
    python3 -m unittest discover -s tests -v

Two kinds of test here:
  - Synthetic-data tests (TestNormalPValue, TestFitClusteredLogit,
    TestBuildPairedDataset) need no external data and always run. They check
    the statistics engine itself: does IRLS recover a known coefficient, does
    the cluster correction actually behave differently from a naive fit, does
    the initial->re-inspection pairing logic handle a hand-built mini example
    correctly.
  - TestFullPipelineRegression re-runs the real analysis against
    data/restaurant-analysis/restaurant_data.json and checks the headline
    numbers against outputs/reinspection_model_results.txt. It's skipped
    automatically when that (gitignored, ~50MB) file isn't present locally --
    regenerate it with data/restaurant-analysis/download_data.py to enable it.
"""
from __future__ import annotations

import json
import sys
import unittest
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from regression import (  # noqa: E402
    build_paired_dataset,
    design_matrix,
    fit_clustered_logit,
    normal_p_value,
)

DATA = Path(__file__).resolve().parent.parent / "data" / "restaurant-analysis" / "restaurant_data.json"
SAVED_RESULTS = Path(__file__).resolve().parent.parent / "outputs" / "reinspection_model_results.txt"


class TestNormalPValue(unittest.TestCase):
    def test_zero_is_certain(self):
        self.assertAlmostEqual(normal_p_value(0.0), 1.0, places=9)

    def test_standard_thresholds(self):
        # z = 1.959964 is the two-sided 5% critical value by construction.
        self.assertAlmostEqual(normal_p_value(1.959964), 0.05, places=4)
        self.assertAlmostEqual(normal_p_value(2.575829), 0.01, places=4)

    def test_symmetric_in_sign(self):
        self.assertAlmostEqual(normal_p_value(1.5), normal_p_value(-1.5), places=9)


class TestFitClusteredLogit(unittest.TestCase):
    """Exercises the hand-rolled IRLS fit and its cluster-robust SEs on
    synthetic data with a known answer, independent of the real dataset."""

    def setUp(self):
        # unittest resets warning filters to "always" per test, which would
        # otherwise re-surface the benign Apple-Accelerate matmul warning
        # that regression.py already suppresses for normal (non-test) runs.
        warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

    def test_recovers_known_coefficients(self):
        rng = np.random.default_rng(0)
        n = 4000
        x1 = rng.normal(size=n)
        x2 = rng.normal(size=n)
        true_beta = np.array([-0.3, 0.8, -0.5])  # intercept, x1, x2
        X = np.column_stack([np.ones(n), x1, x2])
        p = 1 / (1 + np.exp(-(X @ true_beta)))
        y = rng.binomial(1, p)
        clusters = pd.Series(np.arange(n))  # one observation per cluster

        beta, se, cov, g, n_obs = fit_clustered_logit(X, y, clusters)

        self.assertEqual(g, n)
        self.assertEqual(n_obs, n)
        np.testing.assert_allclose(beta, true_beta, atol=0.15)
        # Standard errors should be positive and roughly the expected scale
        # for n=4000 (not near-zero, not blown up).
        self.assertTrue(np.all(se > 0))
        self.assertTrue(np.all(se < 0.5))

    def test_clustering_ignores_fake_duplicate_information(self):
        """If every observation is copied 3x within the same cluster, a
        naive (non-clustered) fit would treat that as 3x the information and
        shrink its standard errors by about sqrt(3). A correct cluster
        correction should recognize the copies carry no new information and
        leave standard errors roughly where they were -- this is the
        textbook check that clustering is actually doing something, not a
        no-op that happens to match analyze_reinspection_model.py's output
        format without changing behavior."""
        rng = np.random.default_rng(1)
        n = 800
        x1 = rng.normal(size=n)
        true_beta = np.array([0.1, 0.6])
        X = np.column_stack([np.ones(n), x1])
        p = 1 / (1 + np.exp(-(X @ true_beta)))
        y = rng.binomial(1, p)
        clusters = pd.Series(np.arange(n))

        _, se_original, _, _, _ = fit_clustered_logit(X, y, clusters)

        X_dup = np.repeat(X, 3, axis=0)
        y_dup = np.repeat(y, 3, axis=0)
        clusters_dup = pd.Series(np.repeat(np.arange(n), 3))
        _, se_duplicated, _, g_dup, n_dup = fit_clustered_logit(X_dup, y_dup, clusters_dup)

        self.assertEqual(g_dup, n)  # still only n distinct clusters
        self.assertEqual(n_dup, 3 * n)
        # Naive iid SE would shrink to roughly se_original / sqrt(3) (~0.58x).
        # The cluster-robust SE should stay close to the original instead.
        ratio = se_duplicated / se_original
        self.assertTrue(np.all(ratio > 0.75), f"clustered SE shrank too much: ratio={ratio}")
        self.assertTrue(np.all(ratio < 1.35), f"clustered SE grew unexpectedly: ratio={ratio}")


class TestBuildPairedDataset(unittest.TestCase):
    """Checks the initial -> re-inspection pairing logic on a small,
    hand-built example instead of the real 50MB extract."""

    def _row(self, camis, boro, cuisine, itype, date, score=None, grade=None):
        return {
            "camis": camis, "boro": boro, "cuisine_description": cuisine,
            "inspection_type": itype, "inspection_date": date,
            "score": score, "grade": grade,
        }

    def test_pairs_reinspection_with_most_recent_prior_initial(self):
        rows = [
            self._row("1", "Manhattan", "American", "Cycle Inspection / Initial Inspection", "2023-01-01", score="10"),
            self._row("1", "Manhattan", "American", "Cycle Inspection / Re-inspection", "2023-02-01", grade="A"),
            # Second restaurant: an initial with no following re-inspection should not appear.
            self._row("2", "Queens", "Pizza", "Cycle Inspection / Initial Inspection", "2023-01-01", score="20"),
        ]
        raw = pd.DataFrame(rows)
        df = build_paired_dataset(raw)

        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["camis"], "1")
        self.assertEqual(df.iloc[0]["borough"], "Manhattan")
        self.assertEqual(df.iloc[0]["initial_score"], 10.0)
        self.assertEqual(df.iloc[0]["grade"], "A")
        self.assertEqual(df.iloc[0]["b_or_c"], 0)

    def test_drops_ungraded_and_out_of_scope_rows(self):
        rows = [
            # No letter grade recorded -> dropped.
            self._row("1", "Manhattan", "American", "Cycle Inspection / Initial Inspection", "2023-01-01", score="10"),
            self._row("1", "Manhattan", "American", "Cycle Inspection / Re-inspection", "2023-02-01", grade=None),
            # boro "0" is not a real borough -> dropped.
            self._row("2", "0", "Pizza", "Cycle Inspection / Initial Inspection", "2023-01-01", score="5"),
            self._row("2", "0", "Pizza", "Cycle Inspection / Re-inspection", "2023-02-01", grade="B"),
        ]
        raw = pd.DataFrame(rows)
        df = build_paired_dataset(raw)
        self.assertEqual(len(df), 0)

    def test_design_matrix_shape_matches_columns(self):
        rows = [
            self._row("1", "Manhattan", "American", "Cycle Inspection / Initial Inspection", "2023-01-01", score="10"),
            self._row("1", "Manhattan", "American", "Cycle Inspection / Re-inspection", "2023-02-01", grade="A"),
            self._row("2", "Bronx", "Pizza", "Cycle Inspection / Initial Inspection", "2023-01-01", score="20"),
            self._row("2", "Bronx", "Pizza", "Cycle Inspection / Re-inspection", "2023-03-01", grade="B"),
        ]
        raw = pd.DataFrame(rows)
        df = build_paired_dataset(raw)
        X, columns = design_matrix(df)
        self.assertEqual(X.shape, (len(df), len(columns)))
        self.assertEqual(columns[0], "Intercept")


@unittest.skipUnless(DATA.exists(), f"regenerate {DATA} with data/restaurant-analysis/download_data.py to run this test")
class TestFullPipelineRegression(unittest.TestCase):
    """Re-runs the real model and checks it still matches the saved,
    known-good output -- a regression test in the literal sense."""

    @classmethod
    def setUpClass(cls):
        raw = pd.DataFrame(json.loads(DATA.read_text()))
        cls.df = build_paired_dataset(raw)
        X, columns = design_matrix(cls.df)
        y = cls.df["b_or_c"].to_numpy(float)
        cls.beta, cls.se, cls.covariance, cls.g, cls.n = fit_clustered_logit(X, y, cls.df["camis"])
        cls.columns = columns

    def test_sample_size_matches_saved_baseline(self):
        self.assertEqual(self.n, 14414)
        self.assertEqual(self.g, 11095)

    def test_borough_odds_ratios_match_saved_baseline(self):
        odds = dict(zip(self.columns, np.exp(self.beta)))
        self.assertAlmostEqual(odds["borough_Bronx"], 1.124, places=2)
        self.assertAlmostEqual(odds["borough_Queens"], 1.107, places=2)
        self.assertAlmostEqual(odds["borough_Brooklyn"], 0.979, places=2)
        self.assertAlmostEqual(odds["borough_Staten Island"], 0.864, places=2)

    def test_saved_output_file_is_current(self):
        self.assertTrue(SAVED_RESULTS.exists())
        text = SAVED_RESULTS.read_text()
        self.assertIn("Eligible paired re-inspections: 14414", text)
        self.assertIn("Unique restaurants (clusters): 11095", text)


if __name__ == "__main__":
    unittest.main()
