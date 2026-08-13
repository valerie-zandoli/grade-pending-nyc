"""Restaurant-clustered logistic model for cycle re-inspection grade outcomes."""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from math import erf, sqrt

import numpy as np
import pandas as pd

# Apple Accelerate's BLAS backend emits spurious "divide by zero"/"overflow"
# RuntimeWarnings on some `@` matmuls (reproducible on random data of the
# same shape, unrelated to this dataset) on numpy 2.0.2/arm64. Suppress only
# this narrow category so a real numerical issue elsewhere still surfaces.
warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)


DATA = Path("data/restaurant-analysis/restaurant_data.json")
INITIAL = "Cycle Inspection / Initial Inspection"
REINSPECTION = "Cycle Inspection / Re-inspection"


def normal_p_value(z: float) -> float:
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def main() -> None:
    raw = pd.DataFrame(json.loads(DATA.read_text()))
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
                paired.append(
                    {
                        "camis": camis,
                        "borough": row.boro,
                        "cuisine": row.cuisine_description,
                        "reinspection_year": row.year,
                        "initial_score": prior_initial.score,
                        "grade": row.grade,
                    }
                )

    df = pd.DataFrame(paired)
    # Grade A is the reference outcome; retain only completed letter-grade visits.
    df = df[df["grade"].isin(["A", "B", "C"])].dropna(
        subset=["borough", "cuisine", "initial_score", "reinspection_year"]
    )
    df = df[df["borough"].isin(["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"])]
    df = df[df["reinspection_year"] >= 2016].copy()
    df["b_or_c"] = df["grade"].isin(["B", "C"]).astype(int)
    df["initial_score_10"] = df["initial_score"] / 10.0
    # The extract has only 29 eligible observations before 2022; combine those
    # years to avoid unstable calendar-year coefficients.
    df["year_model"] = df["reinspection_year"].where(
        df["reinspection_year"] >= 2023, "2022 or earlier"
    ).astype(str)

    # Keep cuisine as a control while avoiding unstable single-observation levels.
    cuisine_count = df["cuisine"].value_counts()
    df["cuisine_model"] = df["cuisine"].where(df["cuisine"].map(cuisine_count) >= 20, "Other / rare cuisine")

    design = pd.concat(
        [
            df[["initial_score_10"]],
            pd.get_dummies(df["borough"], prefix="borough", drop_first=False, dtype=float).drop(columns="borough_Manhattan"),
            pd.get_dummies(df["cuisine_model"], prefix="cuisine", drop_first=True, dtype=float),
            pd.get_dummies(df["year_model"], prefix="year", drop_first=True, dtype=float),
        ],
        axis=1,
    )
    X = np.column_stack([np.ones(len(df)), design.to_numpy(float)])
    columns = ["Intercept", *design.columns]
    y = df["b_or_c"].to_numpy(float)

    # Logistic maximum likelihood using iteratively reweighted least squares.
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
    # Cluster-robust sandwich covariance at the restaurant (CAMIS) level.
    cluster_scores = []
    for _, positions in df.groupby("camis").indices.items():
        positions = np.asarray(list(positions))
        cluster_scores.append(X[positions].T @ (y[positions] - mu[positions]))
    meat = sum(np.outer(s, s) for s in cluster_scores)
    g, n, p = len(cluster_scores), len(df), X.shape[1]
    covariance = bread @ meat @ bread * (g / (g - 1)) * ((n - 1) / (n - p))
    se = np.sqrt(np.diag(covariance))

    result = pd.DataFrame({"term": columns, "odds_ratio": np.exp(beta), "ci_low": np.exp(beta - 1.96 * se), "ci_high": np.exp(beta + 1.96 * se), "p_value": [normal_p_value(b / s) for b, s in zip(beta, se)]})
    borough_result = result[result.term.str.startswith("borough_")].copy()
    borough_result["borough"] = borough_result.term.str.removeprefix("borough_")

    print(f"Eligible paired re-inspections: {n}")
    print(f"Unique restaurants (clusters): {g}")
    print(f"B/C outcome rate: {y.mean() * 100:.1f}%")
    print("\nBorough odds ratios, relative to Manhattan (adjusted for prior score, cuisine, and re-inspection year):")
    print(borough_result[["borough", "odds_ratio", "ci_low", "ci_high", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nPrior-score effect (per 10 points):")
    print(result[result.term == "initial_score_10"][["odds_ratio", "ci_low", "ci_high", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\nStandardized predicted probability of an A grade at re-inspection:")
    borough_columns = {name.removeprefix("borough_"): columns.index(name) for name in columns if name.startswith("borough_")}
    for borough in ("Manhattan", "Bronx", "Queens"):
        counterfactual = X.copy()
        for position in borough_columns.values():
            counterfactual[:, position] = 0
        if borough != "Manhattan":
            counterfactual[:, borough_columns[borough]] = 1
        probability_bc = 1 / (1 + np.exp(-np.clip(counterfactual @ beta, -30, 30)))
        probability_a = 1 - probability_bc
        estimate = probability_a.mean()
        gradient = (-(probability_bc * (1 - probability_bc))[:, None] * counterfactual).mean(axis=0)
        standard_error = float(np.sqrt(gradient @ covariance @ gradient))
        print(f"{borough}: {estimate:.4f} ({estimate - 1.96 * standard_error:.4f}, {estimate + 1.96 * standard_error:.4f})")


if __name__ == "__main__":
    main()
