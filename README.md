# Grade Pending NYC

**57% of cited Manhattan restaurants re-grade to an A. In the Bronx and Queens,
it's 50% — even after adjusting for how bad the citation was, cuisine, and
timing.** That gap is a signal worth DOHMH's attention, not borough noise.

A restaurant-clustered logistic regression on NYC DOHMH re-inspection outcomes,
built during week 6 of enrollment in Pursuit's AI Native program.

> **This README is the canonical write-up.** [`index.html`](index.html) is the
> same finding as a shareable one-page site (open it directly, or serve it
> locally — see Contents below). [`INVESTIGATION.md`](INVESTIGATION.md) is the
> technical appendix on *why* the gap exists. [`NOTES.md`](NOTES.md) is a data
> reference, not a narrative. [`01ChatGradePending.md`](01ChatGradePending.md)
> is a raw, unedited transcript of an earlier working session, kept for
> process transparency — it's an archival log, not a maintained document, and
> nothing in it should be treated as more current than what's written here.

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
- [`regression.py`](regression.py) — the shared statistics module: the
  initial→re-inspection pairing logic, the hand-rolled IRLS logistic fit, and
  the restaurant-clustered standard errors. Both scripts below import it
  rather than each keeping their own copy.
- [`analyze_reinspection_model.py`](analyze_reinspection_model.py) — the
  restaurant-clustered logistic regression described above.
- [`investigate_borough_gap.py`](investigate_borough_gap.py) /
  [`investigate_deeper_mechanisms.py`](investigate_deeper_mechanisms.py) —
  the two-round mechanism hunt behind [`INVESTIGATION.md`](INVESTIGATION.md).
- [`tests/test_regression.py`](tests/test_regression.py) /
  [`tests/test_borough_gap.py`](tests/test_borough_gap.py) — automated tests
  for `regression.py` and `investigate_borough_gap.py` respectively; see
  Testing below.
- [`.github/workflows/tests.yml`](.github/workflows/tests.yml) — runs the
  test suite on every push/PR once this repo has a GitHub remote.

## Running the analysis

```bash
python3 data/restaurant-analysis/download_data.py    # first: pulls the 50k-row extract these need
python3 analyze_reinspection_model.py                # the headline borough-adjusted model
python3 investigate_borough_gap.py                   # round 1 of the mechanism hunt
python3 investigate_deeper_mechanisms.py             # round 2 of the mechanism hunt
```

All three exit with a clear message (not a traceback) if you skip the first step.

Results are also saved to [`outputs/reinspection_model_results.txt`](outputs/reinspection_model_results.txt)
and [`outputs/deeper_mechanisms_results.txt`](outputs/deeper_mechanisms_results.txt).

## Testing

```bash
python3 -m unittest discover -s tests -v
```

- [`tests/test_regression.py`](tests/test_regression.py) — the shared
  statistics module: does the logistic fit recover a known coefficient on
  synthetic data, does the cluster correction actually behave differently
  from a naive fit, does the pairing logic handle a small hand-built example
  correctly.
- [`tests/test_borough_gap.py`](tests/test_borough_gap.py) — round 1's own
  logic: the structural-violation classifier, the initial-visit violation
  load aggregation, and the initial→re-inspection gap/recurrence pairing.
- [`tests/test_supabase_load_data.py`](tests/test_supabase_load_data.py) —
  the Supabase loader's `clean_row()` (column selection, score coercion).
  No network or credentials needed; `supabase/load_data.py` imports
  `dotenv`/`supabase` lazily inside `main()` specifically so this file
  doesn't require `supabase/requirements.txt` to be installed.

Most tests need no data and always run. A few (marked with `skipUnless`) only
run if you've generated `data/restaurant-analysis/restaurant_data.json` via
`download_data.py`, and check the full pipeline against the numbers saved in
`outputs/`.

**CI:** [`.github/workflows/tests.yml`](.github/workflows/tests.yml) runs the
full suite on every push and pull request once this repo has a GitHub
remote — compiles every script, then runs the test suite above. It doesn't
fetch `restaurant_data.json` (50MB, regenerable, gitignored on purpose), so
the data-gated tests skip there by design; everything else runs for real on
every push.

## Supabase (groundwork, not yet live)

[`supabase/`](supabase/) has a schema and a loader script for putting the raw
inspection data into a real Postgres database via Supabase, as groundwork for
a possible future live version of the site. **Nothing else in this repo uses
it yet** — `index.html` still has its numbers baked in, and the analysis
scripts still read the local JSON files directly. This is not deployed
anywhere.

Setup (you'll need to do steps 1–3 yourself in the Supabase dashboard — I
can't create an account or project for you):

1. Create a free project at [supabase.com](https://supabase.com).
2. In that project's SQL editor, run [`supabase/schema.sql`](supabase/schema.sql)
   once — it creates a single `inspections` table matching the raw NYC feed's
   own row grain (one row per violation cited on one inspection, same as
   the JSON extract — see [`NOTES.md`](NOTES.md)).
3. Project Settings → API: copy the Project URL and the `service_role` key.
4. Copy [`.env.example`](.env.example) to `.env` (gitignored) and fill in
   `SUPABASE_URL` and `SUPABASE_KEY` with those values.
5. `pip install -r supabase/requirements.txt` (kept separate from the root
   `requirements.txt` so installing the core analysis doesn't pull in
   Supabase's client libraries until you actually want them).
6. `python3 supabase/load_data.py --sample` to load the 1,000-row sample
   first and confirm the connection works, then `python3 supabase/load_data.py`
   for the full 50,000-row extract.

The loader deliberately uses the `service_role` key (needs write access); a
future live site reading from this table would use the public `anon` key
with row-level security instead, not `service_role`, which should never
reach a browser.

## Limitations

- Single-pull sample, not the full 295k-row table — a fuller extract would
  let the year-bucketing above be un-collapsed.
- Cross-sectional, not causal: a borough's worse odds could reflect
  inspector assignment, restaurant density, reporting lag, or unmeasured
  neighborhood factors, not something intrinsic to the borough itself.
- Cuisine categories with fewer than 20 observations are folded into "Other"
  to avoid unstable single-cell estimates, which trades cuisine-level detail
  for model stability the same way the year-bucketing does.

## License

Code is [MIT licensed](LICENSE). The underlying data is [NYC DOHMH
Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j.json),
published by NYC Open Data under its own open-data terms — the MIT license
here covers this repo's code, not the city's dataset.
