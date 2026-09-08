// Checks pairing.js's buildPairedDataset/designMatrix against the trusted
// Python pipeline (regression.py's same-named functions), run on an
// identical raw-row subset -- rather than trusting a fresh JavaScript port
// of pairing/dummy-encoding logic on its own.
//
// Needs a fixture pairing a raw-row subset with Python's own output on that
// subset. Regenerate with (from the repo root, with restaurant_data.json
// already present):
//
//   python3 -c "
//   import json
//   import pandas as pd
//   from regression import build_paired_dataset, design_matrix
//   raw_all = pd.DataFrame(json.loads(open('data/restaurant-analysis/restaurant_data.json').read()))
//   full_paired = build_paired_dataset(raw_all)
//   subset_camis = set(full_paired['camis'].astype(str).drop_duplicates().head(400))
//   raw_all['camis_str'] = raw_all['camis'].astype(str)
//   raw_subset = raw_all[raw_all['camis_str'].isin(subset_camis)].drop(columns=['camis_str'])
//   paired_subset = build_paired_dataset(raw_subset)
//   X, columns = design_matrix(paired_subset)
//   json.dump({
//       'raw_rows': json.loads(raw_subset.to_json(orient='records')),
//       'expected_paired': json.loads(paired_subset.to_json(orient='records')),
//       'expected_X': X.tolist(),
//       'expected_columns': columns,
//   }, open('/tmp/pairing_fixture.json', 'w'))
//   "
const fs = require("fs");
const { buildPairedDataset, designMatrix } = require("../pairing.js");

const FIXTURE_PATH = "/tmp/pairing_fixture.json";

if (!fs.existsSync(FIXTURE_PATH)) {
  console.log(`SKIPPED: ${FIXTURE_PATH} not found -- see the comment at the top of this file to regenerate it.`);
  process.exit(0);
}

const { raw_rows, expected_paired, expected_X, expected_columns } = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8"));

let failures = 0;
function check(name, pass, detail) {
  console.log(`${pass ? "ok" : "FAIL"} -- ${name}${detail ? `: ${detail}` : ""}`);
  if (!pass) failures++;
}

const df = buildPairedDataset(raw_rows);

check("paired row count", df.length === expected_paired.length, `got ${df.length}, expected ${expected_paired.length}`);

const PAIRED_FIELDS = ["camis", "borough", "cuisine", "reinspection_year", "initial_score", "grade", "b_or_c", "initial_score_10", "year_model", "cuisine_model"];
let fieldMismatches = 0;
for (let i = 0; i < Math.min(df.length, expected_paired.length); i++) {
  for (const field of PAIRED_FIELDS) {
    const got = df[i][field];
    const want = expected_paired[i][field];
    const bothNumbers = typeof got === "number" && typeof want === "number";
    const same = bothNumbers ? Math.abs(got - want) < 1e-9 : got === want;
    if (!same) {
      fieldMismatches++;
      if (fieldMismatches <= 5) console.log(`  row ${i} field ${field}: got ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
    }
  }
}
check("paired field values match row-for-row", fieldMismatches === 0, `${fieldMismatches} mismatches`);

const { X, columns } = designMatrix(df);

check("design matrix column count", columns.length === expected_columns.length, `got ${columns.length}, expected ${expected_columns.length}`);
check("design matrix column names match", JSON.stringify(columns) === JSON.stringify(expected_columns), JSON.stringify(columns) !== JSON.stringify(expected_columns) ? `got ${JSON.stringify(columns)}` : "");

let cellMismatches = 0;
for (let i = 0; i < Math.min(X.length, expected_X.length); i++) {
  for (let j = 0; j < Math.min(X[i].length, expected_X[i].length); j++) {
    if (Math.abs(X[i][j] - expected_X[i][j]) > 1e-9) {
      cellMismatches++;
      if (cellMismatches <= 5) console.log(`  X[${i}][${j}]: got ${X[i][j]}, expected ${expected_X[i][j]}`);
    }
  }
}
check("design matrix values match cell-for-cell", cellMismatches === 0, `${cellMismatches} mismatches`);

if (failures > 0) {
  console.log(`\n${failures} check(s) failed.`);
  process.exit(1);
}
console.log("\nAll checks passed: pairing.js matches the trusted Python pipeline on an identical raw-row subset.");
