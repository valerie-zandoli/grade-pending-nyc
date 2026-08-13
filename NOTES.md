# Grade Pending NYC — dataset notes

Source: NYC DOHMH Restaurant Inspection Results
`https://data.cityofnewyork.us/resource/43nn-pn8j.json`
Full table: 295,054 rows. Sample pulled to `data/sample_1000.json` via `?$limit=1000`.

## What one row is

One row = one violation cited on one inspection. Not one restaurant, not
even one inspection. A restaurant that gets cited for six things on the
same visit produces six rows with the same `camis`, `dba`, and
`inspection_date`, one row per `violation_code`.

If a restaurant passes an inspection with **zero** violations, that
inspection still gets exactly one row — but with no `violation_code`,
`violation_description`, `grade`, or `grade_date`. Counting rows without
grouping first double- (or sextuple-) counts cited restaurants and treats
"inspected once, cited six times" the same as "inspected six times."

## Columns that actually matter

| Column | Why |
|---|---|
| `camis` | The restaurant's real, stable ID. Use this to identify a restaurant, not `dba`. |
| `dba` | The name as typed at inspection time. Free text — not reliable for grouping (see below). |
| `boro` | Title case: `Manhattan`, `Brooklyn`, `Queens`, `Bronx`, `Staten Island`. **Not** `MANHATTAN` — that query silently returns 0 rows, no error. |
| `cuisine_description` | Self-reported category. This is what "worst cuisine" analysis would group by — but see the counting trap above. |
| `inspection_date` | Groups violation rows back into a single inspection visit. |
| `violation_code` / `violation_description` | The actual citation. Absent (not null — the key doesn't exist) on violation-free inspections. |
| `critical_flag` | `Critical` / `Not Critical` / `Not Applicable`. |
| `score` / `grade` / `grade_date` | Inspection score and letter grade, if graded yet. |
| `action` | What happened at the inspection (violations cited, closed, re-opened, etc.). |

Location/admin columns (`bbl`, `bin`, `census_tract`, `community_board`,
`council_district`, `nta`, `:@computed_region_*`) are geo joins, not
needed for a violations-by-cuisine analysis.

## One thing I did not expect

The prompt warned that `DUNKIN` and `DUNKIN'` are separate `dba` values —
that undersold it. A `$where=dba like 'DUNKIN%'` query returns **57
distinct spellings** tied back to a much smaller set of `camis` values,
including `DUNKIN`, `DUNKIN'`, `DUNKIN DONUTS`, `DUNKIN' DONUTS`,
`DUNKIN / BASKIN ROBBINS` (and about a dozen punctuation variants of that
combo), `DUNKIN99`, and multi-tenant food-court entries like
`DUNKIN/JIMMY JOHN'S/QNS MARKET`. `dba` is closer to a free-text label
scrawled at inspection time than a name field — any real analysis has to
key on `camis`.

Also: the live distinct counts don't match the ones quoted in the
assignment (9,453 distinct `dba` / 11,704 distinct `camis`). Right now
the full table has **24,497 distinct `dba` and 31,194 distinct `camis`**
— the dataset has grown since those numbers were written, another sign
this feed is live and not a fixed snapshot.

## Gotchas confirmed by hand

- `boro=Manhattan` → 3 rows returned. `boro=MANHATTAN` → 0 rows, no error, easy to miss.
- Some rows are missing `violation_code`/`grade`/`grade_date` keys entirely (uncited inspections), not just null — code that assumes the key exists will `KeyError`.
