"""Specification checks for the main model in analyze_reinspection_model.py:
is the linear-score, constant-borough-effect assumption right? See
INVESTIGATION.md's "A specification check, held to the same standard"."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from regression import build_paired_dataset, design_matrix, fit_clustered_logit, odds_ratio_table

DATA = Path("data/restaurant-analysis/restaurant_data.json")


def main() -> None:
    if not DATA.exists():
        sys.exit(f"{DATA} not found. Regenerate it with data/restaurant-analysis/download_data.py.")
    raw = pd.DataFrame(json.loads(DATA.read_text()))
    df = build_paired_dataset(raw)
    y = df["b_or_c"].to_numpy(float)

    print("=" * 72)
    print("CHECK 1: multicollinearity -- condition number and borough VIFs")
    print("=" * 72)
    X0, cols0 = design_matrix(df)
    XtX = X0.T @ X0
    eigenvalues = np.linalg.eigvalsh(XtX)
    cond_number = np.sqrt(eigenvalues.max() / eigenvalues[eigenvalues > 1e-10].min())
    print(f"Condition number: {cond_number:.0f} (rule of thumb: <30 fine, 30-100 moderate, >100 severe)")
    design_df = pd.DataFrame(X0[:, 1:], columns=cols0[1:])
    other_cols = [c for c in design_df.columns if not c.startswith("borough_")]
    for col in ["borough_Bronx", "borough_Brooklyn", "borough_Queens", "borough_Staten Island"]:
        Xo = np.column_stack([np.ones(len(design_df)), design_df[other_cols].values])
        beta, *_ = np.linalg.lstsq(Xo, design_df[col].values, rcond=None)
        r2 = 1 - np.sum((design_df[col].values - Xo @ beta) ** 2) / np.sum((design_df[col].values - design_df[col].mean()) ** 2)
        vif = 1 / (1 - r2) if r2 < 0.999 else float("inf")
        print(f"  {col}: VIF = {vif:.2f}")

    print()
    print("=" * 72)
    print("CHECK 2: nonlinearity in score, and a borough x score interaction")
    print("=" * 72)
    df["initial_score_10_sq"] = df["initial_score_10"] ** 2
    df["borough_Bronx_x_score"] = (df["borough"] == "Bronx").astype(float) * df["initial_score_10"]
    df["borough_Queens_x_score"] = (df["borough"] == "Queens").astype(float) * df["initial_score_10"]
    extra = ["initial_score_10_sq", "borough_Bronx_x_score", "borough_Queens_x_score"]
    X1, cols1 = design_matrix(df, extra_cols=extra)
    beta1, se1, cov1, g1, n1 = fit_clustered_logit(X1, y, df["camis"])
    result1 = odds_ratio_table(beta1, se1, cols1)

    print("Borough main effects (at initial_score=0, not the average effect):")
    main_effects = result1[result1.term.str.startswith("borough_") & ~result1.term.str.contains("_x_")]
    print(main_effects[["term", "odds_ratio", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))
    print()
    print("Nonlinear and interaction terms:")
    interaction_rows = result1[result1.term.str.contains("_x_score|_sq")]
    print(interaction_rows[["term", "odds_ratio", "p_value"]].to_string(index=False, float_format=lambda x: f"{x:.4f}"))

    print()
    print("=" * 72)
    print("CHECK 3: where does the Queens x score effect cross OR=1?")
    print("=" * 72)
    queens_main = beta1[cols1.index("borough_Queens")]
    queens_int = beta1[cols1.index("borough_Queens_x_score")]
    crossover_score = -queens_main / queens_int * 10
    median_score = df["initial_score_10"].median() * 10
    print(f"Queens effective OR crosses 1 at initial score = {crossover_score:.1f}")
    print(f"Median initial score in the paired dataset: {median_score:.0f}")
    for score in [0, 10, 20, 30, 40]:
        log_or = queens_main + queens_int * (score / 10.0)
        print(f"  at score={score}: OR={np.exp(log_or):.3f}")

    print()
    print("=" * 72)
    print("CHECK 4: B vs C grade split by borough (descriptive, unadjusted)")
    print("=" * 72)
    graded = df[df["grade"].isin(["A", "B", "C"])]
    b_only = graded[graded.grade.isin(["A", "B"])].copy()
    b_only["is_b"] = (b_only.grade == "B").astype(int)
    c_only = graded[graded.grade.isin(["A", "C"])].copy()
    c_only["is_c"] = (c_only.grade == "C").astype(int)
    for b in ["Manhattan", "Bronx", "Queens"]:
        sub_b = b_only[b_only.borough == b]
        sub_c = c_only[c_only.borough == b]
        print(f"  {b}: P(B | A or B)={sub_b.is_b.mean():.3f} (n={len(sub_b)})   P(C | A or C)={sub_c.is_c.mean():.3f} (n={len(sub_c)})")


if __name__ == "__main__":
    main()
