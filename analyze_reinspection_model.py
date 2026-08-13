"""Restaurant-clustered logistic model for cycle re-inspection grade outcomes."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from regression import build_paired_dataset, design_matrix, fit_clustered_logit, odds_ratio_table

# Apple Accelerate's BLAS backend emits spurious "divide by zero"/"overflow"
# RuntimeWarnings on some `@` matmuls (reproducible on random data of the
# same shape, unrelated to this dataset) on numpy 2.0.2/arm64. Suppress only
# this narrow category so a real numerical issue elsewhere still surfaces.
warnings.filterwarnings("ignore", message=".*encountered in matmul", category=RuntimeWarning)

DATA = Path("data/restaurant-analysis/restaurant_data.json")


def main() -> None:
    raw = pd.DataFrame(json.loads(DATA.read_text()))
    df = build_paired_dataset(raw)

    X, columns = design_matrix(df)
    y = df["b_or_c"].to_numpy(float)
    beta, se, covariance, g, n = fit_clustered_logit(X, y, df["camis"])

    result = odds_ratio_table(beta, se, columns)
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
