"""Shared statistics used across the re-inspection analysis scripts.

analyze_reinspection_model.py and investigate_deeper_mechanisms.py both build
a restaurant-clustered logistic model on the same paired initial -> re-
inspection dataset. This module is the single implementation of that pairing
logic, the hand-rolled IRLS fit, and the cluster-robust standard errors, so a
fix here reaches every script that uses it instead of needing to be repeated
in each one.
"""
from __future__ import annotations

from math import erf, sqrt

import numpy as np
import pandas as pd

INITIAL = "Cycle Inspection / Initial Inspection"
REINSPECTION = "Cycle Inspection / Re-inspection"
BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]


def normal_p_value(z: float) -> float:
    """Two-sided p-value for a standard-normal z-statistic."""
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def build_paired_dataset(raw: pd.DataFrame, extra_visit_cols: list[str] | None = None) -> pd.DataFrame:
    """Pair each restaurant's cycle re-inspection with its most recent prior
    cycle-initial inspection. One output row per paired visit, filtered to
    graded (A/B/C) outcomes in the five NYC boroughs from 2016 onward.

    extra_visit_cols: additional fields to carry over from the re-inspection
    row (e.g. "community_board" for a density covariate).
    """
    extra_visit_cols = extra_visit_cols or []
    raw = raw[raw["inspection_type"].isin([INITIAL, REINSPECTION])].copy()
    raw["inspection_date"] = pd.to_datetime(raw["inspection_date"])

    # Each original row is one citation; collapse back to one inspection visit.
    visit = (
        raw.sort_values("inspection_date")
        .groupby(["camis", "inspection_date", "inspection_type"], as_index=False)
        .first()
    )
    visit["score"] = pd.to_numeric(visit["score"], errors="coerce")
    visit["year"] = visit["inspection_date"].dt.year

    paired = []
    for camis, group in visit.groupby("camis", sort=False):
        prior_initial = None
        for row in group.sort_values("inspection_date").itertuples(index=False):
            if row.inspection_type == INITIAL:
                prior_initial = row
            elif row.inspection_type == REINSPECTION and prior_initial is not None:
                record = {
                    "camis": camis,
                    "borough": row.boro,
                    "cuisine": row.cuisine_description,
                    "reinspection_year": row.year,
                    "initial_score": prior_initial.score,
                    "grade": row.grade,
                }
                for col in extra_visit_cols:
                    record[col] = getattr(row, col, None)
                paired.append(record)

    df = pd.DataFrame(paired)
    # Grade A is the reference outcome; retain only completed letter-grade visits.
    df = df[df["grade"].isin(["A", "B", "C"])].dropna(
        subset=["borough", "cuisine", "initial_score", "reinspection_year"]
    )
    df = df[df["borough"].isin(BOROUGHS)]
    df = df[df["reinspection_year"] >= 2016].copy()
    df["b_or_c"] = df["grade"].isin(["B", "C"]).astype(int)
    df["initial_score_10"] = df["initial_score"] / 10.0
    # Too few eligible observations before 2023 to estimate stable
    # calendar-year coefficients; bucket them together instead.
    df["year_model"] = df["reinspection_year"].where(
        df["reinspection_year"] >= 2023, "2022 or earlier"
    ).astype(str)
    # Keep cuisine as a control while avoiding unstable single-observation levels.
    cuisine_count = df["cuisine"].value_counts()
    df["cuisine_model"] = df["cuisine"].where(df["cuisine"].map(cuisine_count) >= 20, "Other / rare cuisine")
    return df


def design_matrix(df: pd.DataFrame, extra_cols: list[str] | None = None) -> tuple[np.ndarray, list[str]]:
    """Borough (Manhattan held out) + cuisine + year dummies, plus
    initial_score_10 and any extra numeric covariates, with an intercept."""
    parts = [df[["initial_score_10"]]]
    if extra_cols:
        parts.append(df[extra_cols])
    parts += [
        pd.get_dummies(df["borough"], prefix="borough", drop_first=False, dtype=float).drop(columns="borough_Manhattan"),
        pd.get_dummies(df["cuisine_model"], prefix="cuisine", drop_first=True, dtype=float),
        pd.get_dummies(df["year_model"], prefix="year", drop_first=True, dtype=float),
    ]
    design = pd.concat(parts, axis=1)
    X = np.column_stack([np.ones(len(df)), design.to_numpy(float)])
    columns = ["Intercept", *design.columns]
    return X, columns


def fit_clustered_logit(X: np.ndarray, y: np.ndarray, clusters: pd.Series):
    """Logistic MLE via iteratively reweighted least squares, with a
    cluster-robust sandwich covariance (clustered on `clusters`, e.g. the
    restaurant ID, so repeated visits from the same restaurant don't count as
    independent observations).

    Returns (beta, se, covariance, n_clusters, n_observations).
    """
    def log_likelihood(coefficients: np.ndarray) -> float:
        linear = np.clip(X @ coefficients, -30, 30)
        return float(np.sum(y * linear - np.logaddexp(0, linear)))

    beta = np.zeros(X.shape[1])
    current_ll = log_likelihood(beta)
    for _ in range(100):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        hessian = X.T @ (X * w[:, None])
        score = X.T @ (y - mu)
        step = np.linalg.lstsq(hessian, score, rcond=None)[0]
        # Backtracking keeps IRLS stable when sparse categorical cells create
        # an overly aggressive Newton step.
        multiplier = 1.0
        beta_next = beta + step
        while log_likelihood(beta_next) < current_ll and multiplier > 1e-6:
            multiplier /= 2
            beta_next = beta + multiplier * step
        if np.max(np.abs(multiplier * step)) < 1e-9:
            beta = beta_next
            break
        beta = beta_next
        current_ll = log_likelihood(beta)
    else:
        raise RuntimeError("IRLS did not converge")

    mu = 1 / (1 + np.exp(-np.clip(X @ beta, -30, 30)))
    bread = np.linalg.inv(X.T @ (X * (mu * (1 - mu))[:, None]))
    clusters = pd.Series(clusters).reset_index(drop=True)
    cluster_scores = []
    for _, positions in clusters.groupby(clusters).indices.items():
        positions = np.asarray(list(positions))
        cluster_scores.append(X[positions].T @ (y[positions] - mu[positions]))
    meat = sum(np.outer(s, s) for s in cluster_scores)
    g, n, p = len(cluster_scores), len(y), X.shape[1]
    covariance = bread @ meat @ bread * (g / (g - 1)) * ((n - 1) / (n - p))
    se = np.sqrt(np.diag(covariance))
    return beta, se, covariance, g, n


def odds_ratio_table(beta: np.ndarray, se: np.ndarray, columns: list[str]) -> pd.DataFrame:
    """Term-by-term odds ratios, 95% CI, and p-value."""
    return pd.DataFrame({
        "term": columns,
        "odds_ratio": np.exp(beta),
        "ci_low": np.exp(beta - 1.96 * se),
        "ci_high": np.exp(beta + 1.96 * se),
        "p_value": [normal_p_value(b / s) for b, s in zip(beta, se)],
    })
