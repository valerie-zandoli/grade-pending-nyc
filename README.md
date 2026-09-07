# Grade Pending NYC

**A 50,000-row sample suggested Manhattan restaurants re-grade to an A after
a health-code violation at a significantly higher rate than the Bronx and
Queens. Against the complete 295,048-row population, that gap shrinks by
more than half and misses conventional statistical significance.** The
apparent disparity looks like it was substantially a small-sample artifact —
a finding about replication as much as about restaurant grades. See
[Reproducing this](#reproducing-this) for how that was caught and fixed.
This project also ships a small, live check guarding against that same
failure mode going forward — one a data engineer can reuse directly for
catching a partial pull from any live, paginated feed, not only this one.
See [Reusing this completeness check in another
pipeline](#reusing-this-completeness-check-in-another-pipeline).

A restaurant-clustered logistic regression on NYC DOHMH re-inspection outcomes,
built during week 6 of enrollment in Pursuit's AI Native program.

> **This README is the canonical write-up.** [`index.html`](index.html) is the
> same finding as a shareable one-page site (open it directly, or serve it
> locally — see Contents below). [`INVESTIGATION.md`](INVESTIGATION.md) is the
> technical appendix on *why* an effect this size might exist. [`NOTES.md`](NOTES.md)
> is a data reference, not a narrative. [`01ChatGradePending.md`](01ChatGradePending.md)
> is a raw, unedited transcript of an earlier working session, kept for
> process transparency — it's an archival log, not a maintained document, and
> nothing in it should be treated as more current than what's written here.

## The finding

On 14,414 paired initial→re-inspection visits from the complete NYC DOHMH
extract (11,095 unique restaurants), **Bronx (OR 1.12, 95% CI 0.97–1.30,
p=.110) and Queens (OR 1.11, 95% CI 1.00–1.23, p=.056) restaurants show a
small tendency toward worse odds of a B or C grade at re-inspection than
Manhattan restaurants**, holding prior inspection score, cuisine, and
re-inspection year fixed — but neither clears conventional significance
(Queens sits right at the boundary; Bronx doesn't). In predicted-probability
terms: a restaurant with average characteristics has roughly a 68% chance of
re-grading to an A in Manhattan, versus ~66% in Queens and the Bronx — a
2-point gap, not a 7-point one. Brooklyn (OR 0.98, p=.686) and Staten Island
(OR 0.86, p=.164) remain indistinguishable from Manhattan, as before.

**This is a materially weaker result than an earlier version of this
analysis reported.** A 50,000-row sample — pulled with no date filter and no
explicit sort order, effectively an arbitrary slice of the table — showed a
larger, clearly significant gap: Bronx OR 1.36 (p=.014), Queens OR 1.27
(p=.009), roughly 57% vs. 50%. That result did not hold up once the same
model was run against the complete dataset instead of a sample. See
[Reproducing this](#reproducing-this) below for the full story: why the
original sample wasn't reproducible, why the deterministic sampling
strategies tried next were each biased in ways that mattered specifically
for this paired-visit design, and why pulling the whole table was the fix
that made the result stop moving around.

See [`index.html`](index.html) for this same finding as a one-page site, or
run `python3 analyze_reinspection_model.py` for the raw model output.

## Why might an effect this size exist?

[`INVESTIGATION.md`](INVESTIGATION.md) tests six candidate mechanisms across
two rounds, run against the complete dataset. Round 1 finds no meaningful
difference in initial-citation severity or compliance-window length between
boroughs; it does find that recurring the same violation code at
re-inspection strongly predicts a B/C outcome within every borough — a
real, useful signal about grading generally, though recurrence *rates*
don't differ enough between boroughs to explain a borough-specific gap on
their own. Round 2's restaurant-density proxy attenuates both borough
effects further (Queens sits right at the edge of significance depending on
exact specification, Bronx does not); reporting lag and inspector
assignment remain **untestable** with this public dataset — DOHMH doesn't
publish the fields that would be needed. Given how small and marginal the
underlying effect already is, none of this should be read as "explaining a
gap" so much as "not finding anything that would make an already-marginal
signal look more real."

## Reproducing this

**An earlier version of `download_data.py` pulled 50,000 rows with
`$limit=50000` and no date filter or sort order.** That has two problems,
one about reproducibility and one about validity:

1. **Not reproducible.** Socrata doesn't guarantee stable row ordering for
   `$offset`-based pagination without an explicit `$order`, and the feed is
   live — re-running that script later silently returns a different slice
   than whoever ran it before you got. The specific 57%-vs-50%,
   clearly-significant result quoted in early versions of this README
   can't be regenerated by running the documented reproduction steps.
2. **The fix that seemed obvious made things worse.** Pinning a
   deterministic `$order` to solve (1) requires *some* sort key, and every
   one available here introduces real sampling bias for a paired
   initial→re-inspection design: ordering by `inspection_date DESC`
   right-censors the sample — recent initial inspections haven't had time
   to get re-inspected yet, which collapsed the paired sample from 3,921 to
   779 re-inspections in testing and inflated every p-value into
   insignificance as a pure artifact of losing 80% of the data, not because
   the effect changed. Ordering by `camis` (restaurant ID) selects only
   long-tenured restaurants, since `camis` is assigned roughly
   chronologically — testing that ordering returned restaurants skewed
   toward a handful of old `camis` ranges, nothing like the current
   restaurant population.

The fix: `download_data.py` now pulls the **complete table** (paginated,
~295k rows) bounded only by a `SNAPSHOT_CUTOFF` date, with a deterministic
`$order` used purely to make pagination stable — not to pick a biased
subset, since there's no subset being picked. Re-running it returns the
same rows every time (verified across three separate pulls). This is also
why every number in this README changed from an earlier version: the
weaker, non-significant result above is what the complete population
actually shows, not a different sample. See Running the analysis below for
the commands.

### Reusing this completeness check in another pipeline

The same failure mode above — a paginated pull that stops early and hands
a downstream calculation a partial dataset instead of failing loudly — is
not specific to restaurant grades or to this feed. Any pipeline pulling
from a live, paginated source can hit it. [`live-check.js`](live-check.js)
is a small, working example of the guard: before a calculation runs, it
sends a single, fast count query (`$select=count(*)`) to the source feed
and compares the result against the last confirmed complete count. Below
that count, it halts with no result shown, rather than letting a partial
pull quietly produce a confident, wrong-looking number the way an earlier
version of this project once did. The pattern generalizes directly:
one cheap count check, one stored baseline, one hard stop — ahead of
whatever calculation the pipeline actually cares about.

## Modeling choice worth flagging

**Pre-2023 re-inspections are collapsed into a single "2022 or earlier"
category instead of one dummy per year.** The reason: several individual
years (2020: 6 eligible re-inspections, 2021: 2) are still too sparse to
estimate stable year-by-year coefficients even in the complete dataset — a
handful of single-observation year cells would otherwise dominate the fit
or fail to converge. Bucketing trades year-level granularity for stability.
This doesn't affect the borough estimates directly, since year is a control
rather than the variable of interest, but it does mean the model can't say
whether the (already marginal) borough effect has been widening, narrowing,
or holding steady over time.

## Data

Source: [NYC DOHMH Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j.json)
— the complete table as of the pinned snapshot date (~295k rows; one row is
one violation cited on one inspection, not one restaurant or one visit —
see [`NOTES.md`](NOTES.md) for the data-quality pitfalls this matters for,
including why `dba` can't be used to identify a restaurant and why borough
capitalization silently zeroes out API queries).

## Setup

```bash
pip install -r requirements.txt
```

## Contents

- [`index.html`](index.html) / [`styles.css`](styles.css) / [`main.js`](main.js) —
  a static one-page site presenting this write-up, deployable as-is to
  GitHub Pages or any static host.
- [`live-check.html`](live-check.html) / [`live-check.js`](live-check.js) —
  checks the live feed's row count for completeness before any future
  live recompute runs against it; see [Reusing this completeness check in
  another pipeline](#reusing-this-completeness-check-in-another-pipeline).
- [`NOTES.md`](NOTES.md) — source data structure and gotchas.
- [`data/sample_1000.json`](data/sample_1000.json) — 1,000-row raw sample.
- [`data/by_camis.json`](data/by_camis.json) — derived summary of 969
  restaurants, keyed by `camis` (the stable restaurant ID).
- [`data/restaurant-analysis/download_data.py`](data/restaurant-analysis/download_data.py) —
  pulls the complete table (paginated, ~295k rows, bounded by a pinned
  `SNAPSHOT_CUTOFF` date for reproducibility — see Reproducing this above)
  into `restaurant_data.json` in that same directory (gitignored, ~270MB,
  too large to track; regenerate with `python3 data/restaurant-analysis/download_data.py`
  from the repo root, same as "Running the analysis" below — the script
  writes next to itself regardless of where you run it from).
- [`regression.py`](regression.py) — the shared statistics module: the
  initial→re-inspection pairing logic, the hand-rolled IRLS logistic fit, and
  the restaurant-clustered standard errors. Every script below imports it
  rather than each keeping their own copy.
- [`analyze_reinspection_model.py`](analyze_reinspection_model.py) — the
  restaurant-clustered logistic regression described above.
- [`investigate_borough_gap.py`](investigate_borough_gap.py) /
  [`investigate_deeper_mechanisms.py`](investigate_deeper_mechanisms.py) —
  the two-round mechanism hunt behind [`INVESTIGATION.md`](INVESTIGATION.md).
- [`check_model_specification.py`](check_model_specification.py) — tests the
  main model's functional-form assumptions (linear score effect, constant
  borough effect); see INVESTIGATION.md's "A specification check, held to
  the same standard."
- [`tests/test_regression.py`](tests/test_regression.py) /
  [`tests/test_borough_gap.py`](tests/test_borough_gap.py) — automated tests
  for `regression.py` and `investigate_borough_gap.py` respectively; see
  Testing below.
- [`.github/workflows/tests.yml`](.github/workflows/tests.yml) — runs the
  test suite on every push/PR once this repo has a GitHub remote.

## Running the analysis

```bash
python3 data/restaurant-analysis/download_data.py    # first: pulls the complete ~295k-row table (~1 minute)
python3 analyze_reinspection_model.py                # the headline borough-adjusted model (~15s)
python3 investigate_borough_gap.py                   # round 1 of the mechanism hunt (~25s)
python3 investigate_deeper_mechanisms.py             # round 2 of the mechanism hunt (~15s)
python3 check_model_specification.py                 # specification checks, see INVESTIGATION.md (~15s)
```

All four exit with a clear message (not a traceback) if you skip the first step.
None of them print anything while they're working (`investigate_borough_gap.py`
in particular used to sit silent for 46 of its ~49 seconds against the
complete dataset, purely from an accidental O(restaurants × visits) filter
inside its main loop — fixed once found; the remaining time is inherent to
iterating ~31k restaurants in Python, not another bug). If a script goes
quiet for a while, that's expected, not stuck.

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
fetch `restaurant_data.json` (~270MB, regenerable, gitignored on purpose), so
the data-gated tests skip there by design; everything else runs for real on
every push. CI runs on Python 3.11; local development was on 3.9 —
both `pandas==2.3.3` and `numpy==2.0.2` declare `>=3.9` support and ship
wheels for both, but this hasn't been verified by an actual 3.11 run
outside CI itself.

**Keeping dependencies current:** [`.github/dependabot.yml`](.github/dependabot.yml)
checks monthly for newer versions of the pinned packages (root and
`supabase/` `requirements.txt`) and the GitHub Actions used in CI, opening a
PR for each rather than either silently drifting or floating unpinned.
Pinning exact versions was a deliberate reproducibility choice (see
Reproducing this above) — Dependabot makes "pinned" mean "a reviewed
decision to update," not "frozen forever."

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
   for the complete ~295k-row table. Check your project's free-tier database
   storage limit before the full load — the sample alone is enough to
   confirm the schema and connection without using much of it.

The loader deliberately uses the `service_role` key (needs write access); a
future live site reading from this table would use the public `anon` key
with row-level security instead, not `service_role`, which should never
reach a browser.

## What is next for the live check

The next two weeks of build time go to onboarding, not to a journalist-facing
dashboard or a standalone, reusable library, even though both are real
requests from real people. Usage data shows nearly every visitor bounces
before reaching [Reproducing this](#reproducing-this), which means the one
reader this tool exists for, a journalist deciding whether to trust a
finding, likely never sees the reasoning that makes the completeness check
worth trusting. A dashboard would hand her a faster answer to a number she
may not yet know how to weigh; a library would serve the secondary data
engineer audience while that primary relationship stays unproven. Both
requests lose to the same problem underneath them: nobody has shown the
check earns trust yet, only that it runs. The fix is structural, not a new
feature — surfacing the reasoning where a skim actually lands, rather than
past a homepage almost everyone leaves first.

## Limitations

- The headline result is genuinely weak, not strong: Queens sits right at
  the edge of conventional significance
  (p=.056 in the main model, p=.041–.099 depending on exact specification
  in round 2) and Bronx doesn't clear it (p=.110–.128). Read this as "a
  small, inconclusive signal," not as either "confirmed" or "disproven."
- **No multiple-comparisons correction is applied**, and it would make the
  above weaker still. The main model tests four boroughs against Manhattan
  simultaneously; at an uncorrected α=.05 each, the naive chance of at
  least one nominally "significant" result among four is ~18.5%, not 5%.
  A Bonferroni-corrected threshold for four comparisons (α=.0125) is not
  cleared by Bronx *or* Queens. Queens's p=.056 shouldn't be read as
  "almost significant" so much as "unremarkable under multiple testing."
- Cross-sectional, not causal: any real (or apparent) borough effect could
  reflect inspector assignment, restaurant density, reporting lag, or
  unmeasured neighborhood factors, not something intrinsic to the borough
  itself.
- Cuisine categories with fewer than 20 observations are folded into "Other"
  to avoid unstable single-cell estimates, which trades cuisine-level detail
  for model stability the same way the year-bucketing does.
- The main model assumes a linear score effect and a constant borough
  effect across score levels. Both assumptions are testably wrong in ways
  that don't overturn the headline conclusion but do complicate it —
  see [`INVESTIGATION.md`](INVESTIGATION.md#a-specification-check-held-to-the-same-standard),
  read with the same multiple-testing caution as the point above.
- `SNAPSHOT_CUTOFF` in `download_data.py` is a fixed date, not "today" —
  reproducing this analysis exactly requires using that pinned date; pulling
  fresh data from a later cutoff will (correctly) reflect a different,
  larger set of inspections and won't reproduce these exact numbers either,
  for legitimate reasons this time.

## License

Code is [MIT licensed](LICENSE). The underlying data is [NYC DOHMH
Restaurant Inspection Results](https://data.cityofnewyork.us/resource/43nn-pn8j.json),
published by NYC Open Data under its own open-data terms — the MIT license
here covers this repo's code, not the city's dataset.
