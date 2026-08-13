# Why the Bronx/Queens gap? A mechanism hunt

[`analyze_reinspection_model.py`](analyze_reinspection_model.py) establishes
*that* Bronx and Queens restaurants have significantly worse odds of a B/C
re-grade than Manhattan, adjusted for prior score, cuisine, and year. This
script — [`investigate_borough_gap.py`](investigate_borough_gap.py) — tests
three candidate mechanisms against the full local extract
(`data/restaurant-analysis/restaurant_data.json`, 50,000 rows) to see if any
of them explain *why*. Run it with `python3 investigate_borough_gap.py`.

## What was tested, and what didn't hold up

**1. Is the initial citation itself worse in the Bronx/Queens?** No, not
meaningfully. Violation counts, critical-violation counts, and inspection
scores at the initial visit are nearly identical across boroughs (1.29
violations/visit in Manhattan vs. 1.31–1.34 elsewhere). Bronx and Queens
skew somewhat more toward structural/physical-condition violations — pests,
temperature control — (41.5% and 37.9% of visits vs. Manhattan's 36.2%), but
the gap is modest, not the kind of difference that plausibly drives a
7-point re-grade gap by itself.

**2. Do Bronx/Queens restaurants have less time to fix the problem before
re-inspection?** Tested and **ruled out** — in the wrong direction, if
anything. Bronx and Queens restaurants are re-inspected *sooner* (median
124–127 days) than Manhattan (146 days), which would predict a worse, not
better, outcome under a "less time to fix it" theory. But pooled across all
boroughs, faster re-inspection correlates with a slightly *lower* B/C rate
(40.0% for the fastest tercile vs. 44.0% for the slowest), and the
correlation is negligible (r=0.037). Compliance-window length doesn't drive
this.

**3. Are Bronx/Queens restaurants failing to fix the exact same violation
(a "repeat offender" pattern)?** Partially true, but doesn't explain the
overall gap. Bronx restaurants do show a real elevated recurrence rate — the
identical violation code shows up again at re-inspection 16.8% of the time,
vs. 13.8% in Manhattan. But within each borough, recurrence barely moves the
B/C rate (in Queens: 46% B/C when a code recurs vs. 48% when it doesn't) —
so the gap isn't concentrated among repeat offenders. It shows up broadly,
including at restaurants whose re-inspection cited entirely new violations.

## What's left

None of the three mechanisms visible in the public inspection data — citation
severity, compliance-window length, or repeat-violation patterns — account
for the gap. It survives all three. The most likely remaining explanations
(inspector assignment and staffing levels per borough, per-inspector
workload, neighborhood-level factors correlated with a restaurant's borough)
aren't published in this dataset. DOHMH doesn't release inspector IDs or
staffing/assignment data publicly, so this analysis has gone as far as the
public data allows — the honest conclusion is "not explained by anything
observable here," not a confirmed cause.
