// Checks regression.js's fit_clustered_logit port against the already-
// trusted Python result (regression.py, verified in tests/test_regression.py
// and outputs/reinspection_model_results.txt), rather than trusting a fresh
// JavaScript implementation of a numerically delicate fit on its own.
//
// This test needs a fixture of the exact design matrix, outcome, and cluster
// vector regression.py already fits, since regression.js only ports the
// numerical engine, not the pairing/dummy-encoding pipeline in front of it.
// Regenerate the fixture with (from the repo root, with restaurant_data.json
// already present):
//
//   python3 -c "
//   import json
//   import pandas as pd
//   from regression import build_paired_dataset, design_matrix
//   raw = pd.DataFrame(json.loads(open('data/restaurant-analysis/restaurant_data.json').read()))
//   df = build_paired_dataset(raw)
//   X, columns = design_matrix(df)
//   y = df['b_or_c'].to_numpy(float)
//   json.dump({'columns': columns, 'X': X.tolist(), 'y': y.tolist(), 'clusters': df['camis'].astype(str).tolist()}, open('/tmp/regression_fixture.json', 'w'))
//   "
const fs = require("fs");
const path = require("path");
const { fitClusteredLogit, oddsRatioTable } = require("../regression.js");

const FIXTURE_PATH = "/tmp/regression_fixture.json";

// Same baseline tests/test_regression.py checks the Python fit against.
const BASELINE_N = 14414;
const BASELINE_G = 11095;
const BASELINE_ODDS = {
  "borough_Bronx": 1.124,
  "borough_Brooklyn": 0.979,
  "borough_Queens": 1.107,
  "borough_Staten Island": 0.864,
};
const TOLERANCE = 0.001;

if (!fs.existsSync(FIXTURE_PATH)) {
  console.log(`SKIPPED: ${FIXTURE_PATH} not found -- see the comment at the top of this file to regenerate it.`);
  process.exit(0);
}

const { X, y, clusters, columns } = JSON.parse(fs.readFileSync(FIXTURE_PATH, "utf8"));
const { beta, se, g, n } = fitClusteredLogit(X, y, clusters);
const table = oddsRatioTable(beta, se, columns);

let failures = 0;

function check(name, actual, expected, tolerance) {
  const pass = Math.abs(actual - expected) < tolerance;
  console.log(`${pass ? "ok" : "FAIL"} -- ${name}: got ${actual}, expected ${expected}`);
  if (!pass) failures++;
}

check("sample size (n)", n, BASELINE_N, 0.5);
check("cluster count (g)", g, BASELINE_G, 0.5);
for (const [term, expected] of Object.entries(BASELINE_ODDS)) {
  const row = table.find(r => r.term === term);
  check(`odds ratio for ${term}`, row.odds_ratio, expected, TOLERANCE);
}

if (failures > 0) {
  console.log(`\n${failures} check(s) failed.`);
  process.exit(1);
}
console.log("\nAll checks passed: regression.js matches the trusted Python baseline.");
