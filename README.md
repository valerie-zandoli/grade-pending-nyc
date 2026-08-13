# Grade Pending NYC

A data-analysis project on NYC DOHMH restaurant inspection results, built for
week 6 of Pursuit's AI program.

Source: [NYC DOHMH Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j.json)
(295,054 rows; one row = one violation cited on one inspection, not one
restaurant or one visit — see [`NOTES.md`](NOTES.md) for the data-quality
pitfalls this matters for).

## Setup

```bash
pip install -r requirements.txt
```

## Contents

- [`NOTES.md`](NOTES.md) — source data structure and gotchas (borough
  capitalization, `dba` spelling variants, missing-key rows on
  violation-free inspections).
- [`data/sample_1000.json`](data/sample_1000.json) — 1,000-row raw sample.
- [`data/by_camis.json`](data/by_camis.json) — derived summary of 969
  restaurants, keyed by `camis` (the stable restaurant ID).
- [`data/restaurant-analysis/download_data.py`](data/restaurant-analysis/download_data.py) —
  pulls up to 50,000 rows from the public API into
  `restaurant_data.json` (gitignored — regenerate locally with
  `python3 download_data.py` from that directory; ~50MB, too large to track).
- [`analyze_reinspection_model.py`](analyze_reinspection_model.py) — a
  restaurant-clustered logistic regression on paired initial→re-inspection
  visits, estimating each borough's odds of a B/C (vs. A) re-grade relative
  to Manhattan, adjusted for prior score, cuisine, and year.

## Running the analysis

```bash
python3 analyze_reinspection_model.py
```

Results are also saved to [`outputs/reinspection_model_results.txt`](outputs/reinspection_model_results.txt).

## Key finding

On 3,921 paired re-inspections since 2016 (3,462 restaurants), Bronx
(OR 1.36, p=.014) and Queens (OR 1.27, p=.009) restaurants have
significantly worse odds of landing a B or C grade at re-inspection than
Manhattan restaurants, after adjusting for prior inspection score, cuisine,
and year. Brooklyn and Staten Island are not statistically distinguishable
from Manhattan at this sample size.
