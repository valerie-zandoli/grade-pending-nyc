# Why might a Bronx/Queens effect this size exist? A mechanism hunt

*Technical appendix to [`README.md`](README.md), which is the canonical
write-up. Read that first — in particular its "Reproducing this" section,*
*which explains why the numbers here are much smaller than an earlier*
*version of this file reported.* [`analyze_reinspection_model.py`](analyze_reinspection_model.py)
*finds a small borough effect against the complete dataset that sits at or*
*past the edge of conventional significance (Queens p=.056, Bronx p=.110),*
*not the larger, clearly-significant effect an earlier 50,000-row sample*
*showed. This document was originally written to explain that larger*
*effect; it now tests the same candidate mechanisms against the complete*
*dataset, in the same spirit, but the honest framing throughout is "does*
*this move an already-marginal estimate," not "what explains a confirmed*
*gap."*

[`investigate_borough_gap.py`](investigate_borough_gap.py) tests three
candidate mechanisms against the complete local extract
(`data/restaurant-analysis/restaurant_data.json`, ~295k rows). Run it with
`python3 investigate_borough_gap.py`.

## What was tested, and what didn't hold up

**1. Is the initial citation itself worse in the Bronx/Queens?** Not by
much. Initial-visit violation counts run slightly higher in the Bronx and
Queens (3.39 and 3.56 violations/visit) than Manhattan (3.26), and the share
of visits with at least one structural/physical-condition violation —
pests, temperature control, facility condition — is a few points higher too
(74.1% Bronx, 72.0% Queens, vs. Manhattan's 69.0%). Real, but modest
differences, not the kind of gap that would plausibly drive even a 2-point
re-grade difference by itself. (Temperature-control citations are matched
by NYC's "02" violation-code family rather than by keyword, after an
earlier keyword-based version of this check was found — via
`tests/test_borough_gap.py` — to miss ~93% of real temperature citations;
see that test file for the specifics.)

**2. Do Bronx/Queens restaurants have less time to fix the problem before
re-inspection?** Tested and **ruled out** — in the wrong direction, if
anything. Bronx and Queens restaurants are re-inspected *sooner* (median
112 and 119 days) than Manhattan (135 days), which would predict a worse,
not better, outcome under a "less time to fix it" theory. Compliance-window
length doesn't point toward this explaining anything.

**3. Are Bronx/Queens restaurants failing to fix the exact same violation
(a "repeat offender" pattern)?** Partially true, and this one is a real,
useful finding on its own even though it doesn't explain a borough gap.
Recurring the identical violation code at re-inspection is common
everywhere (63–76% of re-inspections across boroughs) and **strongly
predicts a B/C outcome within every borough** — in Queens, 41% B/C when a
code recurs vs. 14% when it doesn't; similar 3x gaps hold in every other
borough. That's a substantive result about what predicts re-grade failure
generally. But it doesn't explain a *borough* effect: recurrence rates are
close enough across boroughs (Manhattan 71.7%, Bronx 75.0%, Queens 75.6%,
Staten Island 62.8% as the outlier) that this isn't what's driving Bronx or
Queens apart from Manhattan specifically. (An earlier pass against a
50,000-row sample had found recurrence *rates* similar to this but the
recurrence→B/C *correlation* far weaker — roughly 0.40 vs. 0.37, barely any
difference. That earlier result looks like it undercounted recurring
violations: the smaller sample sometimes didn't contain every violation row
for a given inspection, so `codes_by_visit` was incomplete for some visits.
The complete dataset doesn't have that problem.)

## Round 1 takeaway

Citation severity and compliance-window length don't point toward
explaining even the small effect that survives in the complete dataset.
Repeat-violation patterns are a real, strong predictor of B/C outcomes
generally, but don't differ enough by borough to explain a borough-specific
effect. None of the three make the Bronx/Queens estimate look more
substantial than it already is (which, per README.md, is not very).

## Round 2: density, reporting lag, inspector assignment

[`investigate_deeper_mechanisms.py`](investigate_deeper_mechanisms.py) tests
the three explanations round 1 couldn't reach. Run it with
`python3 investigate_deeper_mechanisms.py`; full output is saved to
[`outputs/deeper_mechanisms_results.txt`](outputs/deeper_mechanisms_results.txt).

**4. Does restaurant density explain the gap?** The dataset has no true
population-density or foot-traffic field, so this uses the closest available
proxy: the number of distinct restaurants per NYC community board in the
complete extract (69 boards, 1–3,023 restaurants each). Adding
`log(board density)` to the regression attenuates both borough estimates
further: Bronx OR 1.119 → 1.098 (p=.128 → .328), Queens OR 1.116 → 1.105
(p=.041 → .099) — Queens crosses from just past the significance boundary
to clearly not significant.

Community-board density is itself strongly correlated with borough — median
1,323 restaurants per board in Manhattan vs. 439 elsewhere — so, as before,
this is genuinely ambiguous between two readings: density could be a real
confound, or adding a covariate this collinear with borough could simply
widen the standard errors without density doing real explanatory work. The
density term's own effect is close to null on its own (OR 0.988, p=.744),
which leans toward the second reading. **Verdict: doesn't move an
already-weak estimate toward looking more real.**

**5. Does reporting lag (inspection → public posting) explain the gap?**
**Still untestable with this dataset.** `record_date` looks like a
per-inspection publish date but is actually a data-pull timestamp — it takes
only 3 distinct values across the entire ~295k-row extract, all clustered on
the day this snapshot was taken. `grade_date` looked like the alternative,
but it equals `inspection_date` for 100% of the 134,550 graded rows (0-day
"lag" always). Neither field measures what DOHMH actually took to post a
result. Same conclusion as before: this is a genuinely open question, not
answerable from this feed, not a "tested, no effect."

**6. Does inspector assignment or staffing explain the gap?** Still
untestable. All 27 fields in the complete extract were enumerated by hand
(four internal geo-join columns present in an earlier smaller pull don't
appear in this one; irrelevant either way, since none of the 31 or 27 was
ever an inspector/staffing field). Same conclusion as round 1.

## What's left after both rounds

Every mechanism visible in the public inspection data was tested against the
complete dataset. None of them make the Bronx/Queens estimate look more
substantial — if anything, adding density pushes Queens from "just past the
edge of significance" to "clearly not." The honest state of the question,
given README.md's finding that the underlying effect is already small and
largely non-significant: **there isn't a real gap here demanding an
explanation so much as there's a small, mostly-not-significant signal that
none of the available public data makes look any more real.** Inspector
assignment and staffing levels remain the one class of explanation this
public dataset genuinely cannot rule in or out, for a signal that may not
need explaining in the first place.

One more reason not to over-read Queens's p=.056: it's one of four
simultaneous borough comparisons in the main model, none corrected for
multiple testing. At an uncorrected α=.05 per comparison, the chance of at
least one nominally "significant" result among four by chance alone is
~18.5%, not 5% — and a Bonferroni-corrected threshold for four comparisons
(α=.0125) isn't cleared by Bronx or Queens. "Borderline" is the right word
for the uncorrected number; it isn't evidence the effect is nearly real.

## A specification check, held to the same standard

Everything above tests whether *other variables* explain the gap. A
separate question: is the main model's functional form — a linear score
effect, a constant borough effect across score levels — actually right?
Loosening both against the complete dataset:

- **Nonlinearity in score.** Adding a squared `initial_score` term to the
  main model: OR=0.985, p=.004. Real and significant — the relationship
  between initial citation severity and the odds of re-grading to A isn't
  a straight line.
- **Borough × score interaction.** Adding `borough × initial_score` terms
  for Bronx and Queens: Bronx's is not significant (OR=0.976, p=.649).
  Queens's is (OR=1.099, p=.005). Worked through at specific score values,
  this says a Queens restaurant with a clean initial inspection
  (score=0) looks *better* than Manhattan in this specification (OR≈0.84),
  and one with a bad initial inspection (score=40) looks *worse*
  (OR≈1.22) — crossing from favorable to unfavorable right around the
  data's median score (25). Both borough *main effects* in this expanded
  model — now meaning "at score=0," not "on average" — stay
  non-significant (Bronx p=.263, Queens p=.107), so this doesn't overturn
  the "no significant uniform gap" conclusion above; it says that if a
  gap exists, it isn't uniform.

Read this with the same caution as the multiple-comparisons note just
above, more so: this is now a fourth and fifth specification tried against
the same underlying comparison (main model, round 1, round 2, and now a
squared term plus two interaction terms), which is exactly the kind of
exploratory search that inflates false-positive risk beyond what any one
of these p-values reports on its own. Finding one significant interaction
this way is a hypothesis for a dedicated, pre-registered follow-up — not a
confirmed refinement to the headline finding, and not treated as one
anywhere else in this repo.

Two more checks, run for completeness rather than because either changed
the picture: the design matrix's condition number is elevated (395) but
every borough dummy's variance inflation factor against the rest of the
model is ~1.05, so multicollinearity isn't the reason the borough
estimates are what they are. And B/C outcomes — collapsed into one
"not-A" category everywhere else in this repo — split unevenly by borough
in a raw, unadjusted comparison: among restaurants moving off an A grade,
Queens's excess (relative to Manhattan) shows up somewhat more in the C
column (16.5% vs. 12.0% land at C, vs. 27.4% vs. 22.3% at B) than the B
column, a hint that "worse" outcomes may carry more of whatever signal
exists than "somewhat worse" ones — not a tested claim, just a pattern
worth a dedicated ordinal-outcome model if this ever gets revisited.
