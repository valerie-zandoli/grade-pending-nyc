# Why the Bronx/Queens gap? A mechanism hunt

*Technical appendix to [`README.md`](README.md), which is the canonical
write-up of the finding this investigation is chasing an explanation for.*

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

## Round 1 conclusion

None of the three mechanisms visible in the public inspection data — citation
severity, compliance-window length, or repeat-violation patterns — account
for the gap. It survives all three.

## Round 2: density, reporting lag, inspector assignment

[`investigate_deeper_mechanisms.py`](investigate_deeper_mechanisms.py) tests
the three explanations named as "most likely" in round 1. Run it with
`python3 investigate_deeper_mechanisms.py`; full output is saved to
[`outputs/deeper_mechanisms_results.txt`](outputs/deeper_mechanisms_results.txt).

**4. Does restaurant density explain the gap?** The dataset has no true
population-density or foot-traffic field, so this uses the closest available
proxy: the number of distinct restaurants per NYC community board in the
50,000-row extract (68 boards, 1–1,927 restaurants each). Adding
`log(board density)` to the regression **visibly attenuates both borough
effects**: Bronx OR 1.35 → 1.16 (p=.018 → .358), Queens OR 1.28 → 1.20
(p=.007 → .076) — both lose significance at the conventional 0.05 threshold.

That is a real result, but not a clean one. Community-board density is
itself strongly correlated with borough — the median board in Manhattan has
908 restaurants versus 310 elsewhere — so this attenuation is genuinely
ambiguous between two readings: density could be a real confound, or adding
a covariate this collinear with borough could simply widen the standard
errors (both CIs do widen) without density doing real explanatory work.
**Verdict: suggestive, not conclusive.** Density is the first candidate in
either round that visibly moves the estimate, and it's the strongest lead
for follow-up — but it can't be reported as "explains the gap" on this
evidence alone. A cleaner test would need restaurant density measured
independently of borough (e.g., commercial square footage or foot traffic
per census tract) rather than a restaurant count that borough itself drives.

**5. Does reporting lag (inspection → public posting) explain the gap?**
**Untestable with this dataset**, not ruled out. `record_date` looks like a
per-inspection publish date but is actually a data-pull timestamp — it takes
only 3 distinct values across 50,000 rows, all clustered on the day the
extract was downloaded. `grade_date` looked like the alternative, but it
equals `inspection_date` for 100% of the 22,405 graded rows (0-day
"lag" always). Neither field measures what DOHMH actually took to post a
result. This is a genuinely different outcome from "tested, no effect" —
it means the question is still open, just not answerable from this feed.

**6. Does inspector assignment or staffing explain the gap?** Still
untestable. All 31 fields in the extract were enumerated by hand; none
identify an inspector, a team, or a staffing level. Same conclusion as round
1, confirmed directly against the field list rather than assumed.

## What's left after both rounds

Five of six candidate mechanisms are now addressed: three ruled out (round
1), one suggestive-but-ambiguous (density), two confirmed untestable with
public data (reporting lag, inspector assignment). The honest state of the
question: **restaurant density is the strongest lead this analysis has
produced, but it stops at "worth a cleaner test with independent density
data," not "explains the gap."** Inspector assignment and staffing levels —
plausible, common explanations for geographic disparities in public-agency
outcomes — remain outside what DOHMH publishes.
