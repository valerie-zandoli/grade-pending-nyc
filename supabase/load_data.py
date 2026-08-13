"""Load the local NYC DOHMH inspection extract into Supabase.

Groundwork for a possible future live version of the site -- nothing else in
this repo reads from Supabase yet. index.html still uses the numbers baked
in at write time, and the analysis scripts still read the local JSON files
directly. This isn't deployed anywhere.

Setup:
  1. Create a free project at https://supabase.com.
  2. Open the SQL editor for that project and run schema.sql (same
     directory as this file) once, to create the `inspections` table.
  3. Project Settings -> API: copy the Project URL and the service_role
     key. (This loader needs write access, so it uses service_role. A
     future live *site* would use the public anon key plus row-level
     security instead -- never ship the service_role key to a browser.)
  4. Copy .env.example (repo root) to .env and fill in SUPABASE_URL and
     SUPABASE_KEY with the values from step 3. .env is gitignored.
  5. pip install -r supabase/requirements.txt
  6. python3 supabase/load_data.py --sample     (1,000 rows, fast, to check the connection)
     python3 supabase/load_data.py              (the full 50k-row extract)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 500

# Matches supabase/schema.sql. The NYC feed's four `:@computed_region_*`
# columns are internal geo-join IDs that no analysis script in this repo
# uses, so they're dropped here rather than carried into the database.
COLUMNS = [
    "camis", "dba", "boro", "building", "street", "zipcode", "phone",
    "cuisine_description", "inspection_date", "inspection_type", "action",
    "violation_code", "violation_description", "critical_flag", "score",
    "grade", "grade_date", "record_date", "latitude", "longitude",
    "community_board", "council_district", "census_tract", "bin", "bbl", "nta",
]


def clean_row(row: dict) -> dict:
    cleaned = {col: row.get(col) for col in COLUMNS}
    try:
        cleaned["score"] = int(float(cleaned["score"])) if cleaned.get("score") not in (None, "") else None
    except (TypeError, ValueError):
        cleaned["score"] = None
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample", action="store_true", help="load data/sample_1000.json instead of the full extract")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_KEY in .env first -- see the setup steps in this file's docstring.")

    data_path = ROOT / ("data/sample_1000.json" if args.sample else "data/restaurant-analysis/restaurant_data.json")
    if not data_path.exists():
        hint = "" if args.sample else " Regenerate it with data/restaurant-analysis/download_data.py."
        sys.exit(f"{data_path} not found.{hint}")

    rows = [clean_row(r) for r in json.loads(data_path.read_text())]
    print(f"Loading {len(rows)} rows from {data_path.relative_to(ROOT)} into Supabase...")

    client = create_client(url, key)
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        client.table("inspections").insert(batch).execute()
        print(f"  {min(i + BATCH_SIZE, len(rows))}/{len(rows)}")

    print("Done.")


if __name__ == "__main__":
    main()
