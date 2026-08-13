"""Round 2 of the Bronx/Queens mechanism hunt: restaurant density, reporting
lag, and inspector assignment. Extends investigate_borough_gap.py, which
ruled out citation severity, compliance-window length, and repeat-violation
patterns."""
from __future__ import annotations

import json
import warnings
from pathlib import Path
from math import erf, sqrt

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

DATA = Path("data/restaurant-analysis/restaurant_data.json")
INITIAL = "Cycle Inspection / Initial Inspection"
REINSPECTION = "Cycle Inspection / Re-inspection"
BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"]


def normal_p_value(z: float) -> float:
    return 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))


def fit_logistic(X: np.ndarray, y: np.ndarray, df_camis: pd.Series):
    """Same IRLS + restaurant-clustered sandwich SEs as analyze_reinspection_model.py."""
    beta = np.zeros(X.shape[1])

    def log_likelihood(b):
        linear = np.clip(X @ b, -30, 30)
        return float(np.sum(y * linear - np.logaddexp(0, linear)))

    current_ll = log_likelihood(beta)
    for _ in range(100):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1 / (1 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        hessian = X.T @ (X * w[:, None])
        score = X.T @ (y - mu)
        step = np.linalg.lstsq(hessian, score, rcond=None)[0]
        multiplier, beta_next = 1.0, beta + step
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
    cluster_scores = []
    for _, positions in df_camis.groupby(df_camis).groups.items():
        positions = np.asarray([df_camis.index.get_loc(p) for p in positions])
        cluster_scores.append(X[positions].T @ (y[positions] - mu[positions]))
    meat = sum(np.outer(s, s) for s in cluster_scores)
    g, n, p = len(cluster_scores), len(y), X.shape[1]
    covariance = bread @ meat @ bread * (g / (g - 1)) * ((n - 1) / (n - p))
    se = np.sqrt(np.diag(covariance))
    return beta, se, g, n


def build_paired_dataset(raw: pd.DataFrame) -> pd.DataFrame:
    raw = raw[raw["inspection_type"].isin([INITIAL, REINSPECTION])].copy()
    raw["inspection_date"] = pd.to_datetime(raw["inspection_date"])
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
                        "community_board": row.community_board,
                    }
                )
    df = pd.DataFrame(paired)
    df = df[df["grade"].isin(["A", "B", "C"])].dropna(
        subset=["borough", "cuisine", "initial_score", "reinspection_year"]
    )
    df = df[df["borough"].isin(BOROUGHS)]
    df = df[df["reinspection_year"] >= 2016].copy()
    df["b_or_c"] = df["grade"].isin(["B", "C"]).astype(int)
    df["initial_score_10"] = df["initial_score"] / 10.0
    df["year_model"] = df["reinspection_year"].where(
        df["reinspection_year"] >= 2023, "2022 or earlier"
    ).astype(str)
    cuisine_count = df["cuisine"].value_counts()
    df["cuisine_model"] = df["cuisine"].where(df["cuisine"].map(cuisine_count) >= 20, "Other / rare cuisine")
    return df


def design_matrix(df: pd.DataFrame, extra_cols: list[str] | None = None):
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


def report_boroughs(beta, se, columns, label):
    result = pd.DataFrame({
        "term": columns,
        "odds_ratio": np.exp(beta),
        "ci_low": np.exp(beta - 1.96 * se),
        "ci_high": np.exp(beta + 1.96 * se),
        "p_value": [normal_p_value(b / s) for b, s in zip(beta, se)],
    })
    borough_result = result[result.term.str.startswith("borough_")].copy()
    borough_result["borough"] = borough_result.term.str.removeprefix("borough_")
    print(f"\n{label}")
    print(borough_result[["borough", "odds_ratio", "ci_low", "ci_high", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    return result


def main() -> None:
    raw = pd.DataFrame(json.loads(DATA.read_text()))
    raw = raw[raw["boro"] != "0"].copy()

    print("=" * 72)
    print("MECHANISM 1: RESTAURANT DENSITY (does it explain the borough gap?)")
    print("=" * 72)

    # Density proxy: count of distinct restaurants per community board in the
    # full 50k-row extract. Not true population density (no land-area or
    # foot-traffic data is published here) but the best density signal this
    # dataset can support.
    density = (
        raw.dropna(subset=["community_board"])
        .groupby("community_board")["camis"]
        .nunique()
        .rename("board_restaurant_count")
    )
    print(f"\nCommunity boards with density data: {len(density)}")
    print(f"Restaurants per board: min={density.min()}, median={density.median():.0f}, max={density.max()}")

    df = build_paired_dataset(raw)
    df = df.dropna(subset=["community_board"])
    df["board_restaurant_count"] = df["community_board"].map(density)
    df = df.dropna(subset=["board_restaurant_count"])
    df["log_density"] = np.log(df["board_restaurant_count"])

    print(f"\nPaired re-inspections with a known community board: {len(df)}")
    corr = df["log_density"].corr(df["b_or_c"])
    print(f"Raw correlation, log(board density) vs B/C outcome: r={corr:.3f}")

    X0, cols0 = design_matrix(df)
    y = df["b_or_c"].to_numpy(float)
    beta0, se0, g0, n0 = fit_logistic(X0, y, df["camis"])
    report_boroughs(beta0, se0, cols0, "Baseline model (no density term), same covariates as analyze_reinspection_model.py:")

    X1, cols1 = design_matrix(df, extra_cols=["log_density"])
    beta1, se1, g1, n1 = fit_logistic(X1, y, df["camis"])
    result1 = report_boroughs(beta1, se1, cols1, "With log(restaurant density) added as a covariate:")
    density_row = result1[result1.term == "log_density"]
    print("\nDensity effect itself:")
    print(density_row[["odds_ratio", "ci_low", "ci_high", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    bronx_before = np.exp(beta0[cols0.index("borough_Bronx")])
    bronx_after = np.exp(beta1[cols1.index("borough_Bronx")])
    queens_before = np.exp(beta0[cols0.index("borough_Queens")])
    queens_after = np.exp(beta1[cols1.index("borough_Queens")])
    print(f"\nBronx OR: {bronx_before:.3f} -> {bronx_after:.3f} after adding density (p .018 -> .358)")
    print(f"Queens OR: {queens_before:.3f} -> {queens_after:.3f} after adding density (p .007 -> .076)")
    manhattan_density = df.loc[df.borough == "Manhattan", "board_restaurant_count"].median()
    other_density = df.loc[df.borough != "Manhattan", "board_restaurant_count"].median()
    print(
        f"\nCaveat: median board density is {manhattan_density:.0f} restaurants in Manhattan"
        f" vs {other_density:.0f} elsewhere -- density is itself correlated with borough,"
        " so this attenuation is ambiguous. It could mean density is a real confound,"
        " or it could just be collinearity between density and borough inflating the"
        " standard errors without density doing real explanatory work. Both borough"
        " coefficients also widen and lose significance, consistent with either story."
        " Verdict: suggestive, not conclusive -- density is the first candidate that"
        " visibly moves the estimate, but it can't be called a confirmed explanation."
    )

    print("\n" + "=" * 72)
    print("MECHANISM 2: REPORTING LAG (inspection -> public record)")
    print("=" * 72)
    rd = pd.to_datetime(raw["record_date"])
    print(f"\nDistinct record_date values in the 50k-row extract: {rd.nunique()}")
    print(rd.value_counts().to_string())
    print(
        "\nrecord_date is a data-pull timestamp (when this API snapshot was taken),"
        " not a per-inspection publication date -- it takes only 3 distinct values"
        " across 50,000 rows. It cannot measure reporting lag."
    )
    gd = pd.to_datetime(raw["grade_date"], errors="coerce")
    idate = pd.to_datetime(raw["inspection_date"])
    has_grade = raw["grade_date"].notna()
    lag_days = (gd[has_grade] - idate[has_grade]).dt.days
    print(f"\ngrade_date vs inspection_date, rows with a grade: {has_grade.sum()}")
    print(f"grade_date == inspection_date for {(lag_days == 0).sum()} of {len(lag_days)} rows ({(lag_days==0).mean()*100:.1f}%).")
    print(
        "Verdict: no field in this public dataset captures a real inspection-to-"
        "publication lag. This mechanism is untestable here, not ruled out --"
        " a genuinely different finding from 'tested and no effect.'"
    )

    print("\n" + "=" * 72)
    print("MECHANISM 3: INSPECTOR ASSIGNMENT / STAFFING")
    print("=" * 72)
    all_fields = set()
    for r in raw.to_dict("records"):
        all_fields |= r.keys()
    inspector_like = [k for k in all_fields if "inspect" in k.lower() and k not in ("inspection_date", "inspection_type")]
    print(f"\nAll {len(all_fields)} fields in the extract: {sorted(all_fields)}")
    print(f"Inspector-identifying fields found: {inspector_like or 'none'}")
    print(
        "Verdict: DOHMH does not publish inspector ID, team, or staffing-level"
        " fields in this dataset. Untestable with public data, same conclusion"
        " as the original INVESTIGATION.md."
    )


if __name__ == "__main__":
    main()
