import json
from pathlib import Path

import requests

OUTPUT_PATH = Path(__file__).resolve().parent / "restaurant_data.json"

# NYC DOHMH Restaurant Inspection Results -- a live, continuously-updated
# feed, not a static file. Without a date filter, re-running this at a later
# date silently pulls a different, larger table than whoever ran it before
# you got. SNAPSHOT_CUTOFF pins the historical window so this always returns
# the same rows: every inspection record as of that date. Update
# SNAPSHOT_CUTOFF (and regenerate outputs/, README.md, etc.) if you
# deliberately want a fresher analysis -- don't just delete this filter to
# get "whatever's newest".
#
# Pulls the complete table under that cutoff, not a sample: an earlier
# version of this script capped at 50,000 rows with no explicit order,
# which (a) wasn't reproducible -- Socrata doesn't guarantee stable
# ordering for $offset pagination without an explicit $order -- and (b)
# every deterministic ordering we could construct from the available
# fields introduced real sampling bias for this analysis's paired
# initial->re-inspection design: ordering by inspection_date DESC
# right-censors recent initial inspections that haven't had time to get
# re-inspected yet (collapsed the paired sample by ~80% in testing);
# ordering by camis ASC only selects long-tenured restaurants, since camis
# is assigned roughly chronologically. Pulling everything sidesteps the
# question entirely.
SNAPSHOT_CUTOFF = "2026-08-13T23:59:59"

API_ENDPOINT = "https://data.cityofnewyork.us/resource/43nn-pn8j.json"
# Optional. Socrata throttles unauthenticated requests by IP more
# aggressively than token'd ones; six requests for a one-off pull is fine
# without one, but if you're re-running this repeatedly (development,
# testing, a scheduled refresh), get a free token at
# https://data.cityofnewyork.us/profile/app_tokens and paste it here.
APP_TOKEN = ""
PAGE_SIZE = 50000

headers = {
    "X-App-Token": APP_TOKEN
}

all_rows = []
offset = 0
while True:
    params = {
        "$limit": PAGE_SIZE,
        "$offset": offset,
        "$where": f"inspection_date <= '{SNAPSHOT_CUTOFF}'",
        # A stable total order so paginated $offset requests neither skip
        # nor duplicate rows across pages (Socrata's default order isn't
        # guaranteed stable otherwise). camis + inspection_date alone
        # aren't unique -- one inspection visit cites multiple
        # violation_codes as separate rows -- so violation_code is
        # included to fully disambiguate.
        "$order": "camis, inspection_date, violation_code",
    }
    response = requests.get(API_ENDPOINT, headers=headers, params=params)
    response.raise_for_status()
    page = response.json()
    all_rows.extend(page)
    print(f"  fetched {len(all_rows)} rows so far (offset {offset})...")
    if len(page) < PAGE_SIZE:
        break
    offset += PAGE_SIZE

with open(OUTPUT_PATH, "w") as f:
    json.dump(all_rows, f)

print(f"Finished! {len(all_rows)} total rows, written to {OUTPUT_PATH}.")
