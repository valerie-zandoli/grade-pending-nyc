"""Why do Bronx/Queens restaurants re-grade worse than Manhattan?

The regression in analyze_reinspection_model.py establishes THAT an adjusted
gap exists. This script looks for mechanism: does the initial citation itself
look different in the Bronx/Queens (more violations, more critical flags,
harder-to-fix violation types), does the compliance window differ, or do the
same specific violations recur at re-inspection more often there?
"""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

DATA = Path("data/restaurant-analysis/restaurant_data.json")
INITIAL = "Cycle Inspection / Initial Inspection"
REINSPECTION = "Cycle Inspection / Re-inspection"
BOROUGHS = ["Manhattan", "Bronx", "Brooklyn", "Queens", "Staten Island"]

# Violation codes whose descriptions point at physical/structural problems
# (pests, facility condition, equipment) rather than paperwork/procedural
# ones (labeling, permits, posting) — a rough split to test whether Bronx/
# Queens citations skew toward the kind of problem that takes more than a
# quick fix.
STRUCTURAL_KEYWORDS = [
    "vermin", "mice", "rats", "roach", "pest", "evidence of", "harborage",
    "facility not vermin proof", "sewage", "plumbing", "refrigerat",
    "cold holding", "hot holding", "food temperature", "thermometer",
    "ventilation", "lighting", "floors, walls", "ceiling", "wall", "floor",
]


def is_structural(description: str) -> bool:
    if not isinstance(description, str):
        return False
    text = description.lower()
    return any(keyword in text for keyword in STRUCTURAL_KEYWORDS)


def main() -> None:
    raw = pd.DataFrame(json.loads(DATA.read_text()))
    raw = raw[raw["boro"].isin(BOROUGHS)].copy()
    raw["inspection_date"] = pd.to_datetime(raw["inspection_date"])

    cycle = raw[raw["inspection_type"].isin([INITIAL, REINSPECTION])].copy()

    # --- 1. Violation load at the initial inspection: how many distinct
    # violation codes did the visit get cited for, and what fraction were
    # "critical"? (Row-level -> visit-level aggregation, since each row is
    # one violation.)
    initial_rows = cycle[cycle["inspection_type"] == INITIAL].copy()
    initial_rows["is_critical"] = initial_rows["critical_flag"] == "Critical"
    initial_rows["is_structural"] = initial_rows["violation_description"].apply(is_structural)

    visit_load = (
        initial_rows.groupby(["camis", "inspection_date", "boro"])
        .agg(
            n_violations=("violation_code", "count"),
            n_critical=("is_critical", "sum"),
            n_structural=("is_structural", "sum"),
            score=("score", "first"),
        )
        .reset_index()
    )
    visit_load["score"] = pd.to_numeric(visit_load["score"], errors="coerce")

    print("=== Initial-inspection violation load by borough ===")
    print(
        visit_load.groupby("boro")[["n_violations", "n_critical", "n_structural", "score"]]
        .mean()
        .round(2)
        .reindex(BOROUGHS)
    )
    print(
        "\nShare of initial visits with >=1 structural/physical-condition violation "
        "(pests, temperature control, facility condition):"
    )
    visit_load["any_structural"] = visit_load["n_structural"] > 0
    print(visit_load.groupby("boro")["any_structural"].mean().round(3).reindex(BOROUGHS))

    # --- 2. Compliance window: days between initial and re-inspection.
    visit = (
        cycle.sort_values("inspection_date")
        .groupby(["camis", "inspection_date", "inspection_type"], as_index=False)
        .first()
    )
    visit["score"] = pd.to_numeric(visit["score"], errors="coerce")

    gaps = []
    initial_violation_codes = {}
    for camis, group in cycle.groupby("camis", sort=False):
        codes_by_visit = (
            group[group["inspection_type"] == INITIAL]
            .groupby("inspection_date")["violation_code"]
            .apply(lambda s: set(s.dropna()))
        )
        prior_initial = None
        prior_codes = None
        for row in (
            visit[visit["camis"] == camis].sort_values("inspection_date").itertuples(index=False)
        ):
            if row.inspection_type == INITIAL:
                prior_initial = row
                prior_codes = codes_by_visit.get(row.inspection_date, set())
            elif row.inspection_type == REINSPECTION and prior_initial is not None:
                reinspection_codes = set(
                    group[
                        (group["inspection_type"] == REINSPECTION)
                        & (group["inspection_date"] == row.inspection_date)
                    ]["violation_code"].dropna()
                )
                recurring = prior_codes & reinspection_codes if prior_codes else set()
                gaps.append(
                    {
                        "camis": camis,
                        "borough": row.boro,
                        "days_to_reinspect": (row.inspection_date - prior_initial.inspection_date).days,
                        "grade": row.grade,
                        "b_or_c": row.grade in ("B", "C"),
                        "n_prior_codes": len(prior_codes) if prior_codes else 0,
                        "n_recurring_codes": len(recurring),
                        "any_recurring": len(recurring) > 0,
                    }
                )

    gap_df = pd.DataFrame(gaps)
    gap_df = gap_df[gap_df["borough"].isin(BOROUGHS)]
    gap_df = gap_df[(gap_df["days_to_reinspect"] >= 0) & (gap_df["days_to_reinspect"] <= 365)]

    print("\n=== Days between initial inspection and re-inspection, by borough ===")
    print(
        gap_df.groupby("borough")["days_to_reinspect"]
        .agg(["median", "mean", "count"])
        .round(1)
        .reindex(BOROUGHS)
    )

    # --- 3. Do the SAME violation codes recur at re-inspection (the
    # restaurant was cited for the identical problem again), and does that
    # rate differ by borough?
    print("\n=== Share of re-inspections citing at least one violation code that also appeared at the initial visit ===")
    recur = gap_df.groupby("borough").apply(
        lambda d: pd.Series(
            {
                "share_any_recurring_code": d["any_recurring"].mean(),
                "n_paired": len(d),
                "b_or_c_rate": d["b_or_c"].mean(),
            }
        )
    )
    print(recur.round(3).reindex(BOROUGHS))

    print(
        "\nCorrelation check: does a recurring violation code predict a B/C re-grade, "
        "within each borough?"
    )
    for borough in BOROUGHS:
        sub = gap_df[gap_df["borough"] == borough]
        if len(sub) < 20:
            continue
        rate_recur = sub.loc[sub["any_recurring"], "b_or_c"].mean()
        rate_no_recur = sub.loc[~sub["any_recurring"], "b_or_c"].mean()
        print(
            f"  {borough}: B/C rate with recurring code = {rate_recur:.2f} "
            f"(n={sub['any_recurring'].sum()}), without = {rate_no_recur:.2f} "
            f"(n={(~sub['any_recurring']).sum()})"
        )


if __name__ == "__main__":
    main()
