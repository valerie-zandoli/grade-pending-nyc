# Grade Pending NYC

**57% of cited Manhattan restaurants re-grade to an A. In the Bronx and Queens,
it's 50% — even after adjusting for how bad the citation was, cuisine, and
timing.** That gap is a signal worth DOHMH's attention, not borough noise.

A restaurant-clustered logistic regression on NYC DOHMH re-inspection outcomes,
built during week 6 of enrollment in Pursuit's AI Native program.

## The finding

On 3,921 paired initial→re-inspection visits since 2016 (3,462 unique
restaurants), **Bronx (OR 1.36, 95% CI 1.07–1.74, p=.014) and Queens (OR
1.27, 95% CI 1.06–1.52, p=.009) restaurants have significantly worse odds of
landing a B or C grade at re-inspection than Manhattan restaurants**, holding
prior inspection score, cuisine, and re-inspection year fixed. In predicted-
probability terms: a restaurant with average characteristics has roughly a
57% chance of re-grading to an A in Manhattan, versus ~50% in Queens and
~50% in the Bronx. Brooklyn and Staten Island are not statistically
distinguishable from Manhattan at this sample size — the effect isn't
"outer boroughs vs. Manhattan," it's specific to the Bronx and Queens.

See [`index.html`](index.html) for this same finding as a one-page site, or
run `python3 analyze_reinspection_model.py` for the raw model output.

## Why does the gap exist?

[`INVESTIGATION.md`](INVESTIGATION.md) tests six candidate mechanisms across
two rounds. Round 1 rules out worse initial citations, a shorter compliance
window before re-inspection, and repeat violations of the same code — the
gap survives all three. Round 2 tests the three explanations round 1
couldn't reach: restaurant density is the strongest lead so far (adding it
attenuates both borough effects to non-significance, though it's collinear
with borough itself, so this is suggestive rather than conclusive);
reporting lag and inspector assignment turn out to be **untestable** with
this public dataset — DOHMH doesn't publish the fields that would be needed.

## Modeling choice worth flagging

**Pre-2023 re-inspections are collapsed into a single "2022 or earlier"
category instead of one dummy per year.** The reason: after pairing visits
and filtering to graded outcomes, only 29 eligible observations fall before
2023 — too few to estimate stable year-by-year coefficients (a handful of
single-observation year cells would otherwise dominate the fit or fail to
converge). Bucketing trades year-level granularity for stability. This
doesn't affect the borough estimates directly, since year is a control
rather than the variable of interest, but it does mean the model can't say
whether the borough gap has been widening, narrowing, or holding steady over
time — a fully paired, multi-year dataset (rather than this single-pull
sample) would be needed to answer that.

## Data

Source: [NYC DOHMH Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j.json)
(295,054 rows; one row = one violation cited on one inspection, not one
restaurant or one visit — see [`NOTES.md`](NOTES.md) for the data-quality
pitfalls this matters for, including why `dba` can't be used to identify a
restaurant and why borough capitalization silently zeroes out API queries).

## Setup

```bash
pip install -r requirements.txt
```

## Contents

- [`index.html`](index.html) / [`styles.css`](styles.css) / [`main.js`](main.js) —
  a static one-page site presenting this write-up, deployable as-is to
  GitHub Pages or any static host.
- [`NOTES.md`](NOTES.md) — source data structure and gotchas.
- [`data/sample_1000.json`](data/sample_1000.json) — 1,000-row raw sample.
- [`data/by_camis.json`](data/by_camis.json) — derived summary of 969
  restaurants, keyed by `camis` (the stable restaurant ID).
- [`data/restaurant-analysis/download_data.py`](data/restaurant-analysis/download_data.py) —
  pulls up to 50,000 rows from the public API into
  `restaurant_data.json` (gitignored — regenerate locally with
  `python3 download_data.py` from that directory; ~50MB, too large to track).
- [`analyze_reinspection_model.py`](analyze_reinspection_model.py) — the
  restaurant-clustered logistic regression described above.

## Running the analysis

```bash
python3 analyze_reinspection_model.py
```

Results are also saved to [`outputs/reinspection_model_results.txt`](outputs/reinspection_model_results.txt).

## Limitations

- Single-pull sample, not the full 295k-row table — a fuller extract would
  let the year-bucketing above be un-collapsed.
- Cross-sectional, not causal: a borough's worse odds could reflect
  inspector assignment, restaurant density, reporting lag, or unmeasured
  neighborhood factors, not something intrinsic to the borough itself.
- Cuisine categories with fewer than 20 observations are folded into "Other"
  to avoid unstable single-cell estimates, which trades cuisine-level detail
  for model stability the same way the year-bucketing does.
