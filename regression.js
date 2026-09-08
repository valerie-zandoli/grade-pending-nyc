// A JavaScript port of regression.py's fit_clustered_logit: logistic MLE via
// IRLS (iteratively reweighted least squares), with a cluster-robust
// sandwich covariance. Written to match the Python implementation term for
// term, including its exact backtracking and finite-sample correction, so
// its output can be checked against the already-trusted Python baseline
// rather than trusted on its own.

function matVec(X, v) {
  // X: array of row arrays, v: array. Returns X @ v.
  return X.map(row => row.reduce((sum, x, j) => sum + x * v[j], 0));
}

function matTVec(X, v) {
  // X^T @ v, where X is n x p and v is length n. Returns length p.
  const p = X[0].length;
  const out = new Array(p).fill(0);
  for (let i = 0; i < X.length; i++) {
    const xi = X[i], vi = v[i];
    for (let j = 0; j < p; j++) out[j] += xi[j] * vi;
  }
  return out;
}

function xtWx(X, w) {
  // X^T @ (X * w[:, None]) -- weighted Gram matrix, p x p.
  const n = X.length, p = X[0].length;
  const out = Array.from({ length: p }, () => new Array(p).fill(0));
  for (let i = 0; i < n; i++) {
    const xi = X[i], wi = w[i];
    for (let a = 0; a < p; a++) {
      const xia_wi = xi[a] * wi;
      for (let b = 0; b < p; b++) out[a][b] += xia_wi * xi[b];
    }
  }
  return out;
}

function solve(A, b) {
  // Solves A @ x = b via Gaussian elimination with partial pivoting.
  // A: p x p, b: length p. A is not mutated.
  const p = A.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let col = 0; col < p; col++) {
    let pivotRow = col;
    for (let r = col + 1; r < p; r++) {
      if (Math.abs(M[r][col]) > Math.abs(M[pivotRow][col])) pivotRow = r;
    }
    [M[col], M[pivotRow]] = [M[pivotRow], M[col]];
    const pivot = M[col][col];
    for (let r = 0; r < p; r++) {
      if (r === col) continue;
      const factor = M[r][col] / pivot;
      for (let c = col; c <= p; c++) M[r][c] -= factor * M[col][c];
    }
  }
  return M.map((row, i) => row[p] / row[i]);
}

function inverse(A) {
  // A^-1 via solving A @ x_j = e_j for each standard basis vector.
  const p = A.length;
  const cols = [];
  for (let j = 0; j < p; j++) {
    const e = new Array(p).fill(0);
    e[j] = 1;
    cols.push(solve(A, e));
  }
  // cols[j] is column j of the inverse; transpose to row-major.
  const inv = Array.from({ length: p }, () => new Array(p).fill(0));
  for (let i = 0; i < p; i++) for (let j = 0; j < p; j++) inv[i][j] = cols[j][i];
  return inv;
}

function logLikelihood(X, y, beta) {
  let total = 0;
  for (let i = 0; i < X.length; i++) {
    const linear = Math.max(-30, Math.min(30, matVec([X[i]], beta)[0]));
    // logaddexp(0, linear) = log(1 + exp(linear)), computed stably.
    const logaddexp0 = linear > 0 ? linear + Math.log1p(Math.exp(-linear)) : Math.log1p(Math.exp(linear));
    total += y[i] * linear - logaddexp0;
  }
  return total;
}

function fitClusteredLogit(X, y, clusters) {
  const n = X.length, p = X[0].length;
  let beta = new Array(p).fill(0);
  let currentLL = logLikelihood(X, y, beta);
  let converged = false;

  for (let iter = 0; iter < 100; iter++) {
    const eta = X.map(row => Math.max(-30, Math.min(30, matVec([row], beta)[0])));
    const mu = eta.map(e => 1 / (1 + Math.exp(-e)));
    const w = mu.map(m => Math.max(1e-9, m * (1 - m)));
    const hessian = xtWx(X, w);
    const residual = y.map((yi, i) => yi - mu[i]);
    const score = matTVec(X, residual);
    const step = solve(hessian, score);

    let multiplier = 1.0;
    let betaNext = beta.map((b, j) => b + multiplier * step[j]);
    while (logLikelihood(X, y, betaNext) < currentLL && multiplier > 1e-6) {
      multiplier /= 2;
      betaNext = beta.map((b, j) => b + multiplier * step[j]);
    }
    const maxStep = Math.max(...step.map((s, j) => Math.abs(multiplier * s)));
    beta = betaNext;
    if (maxStep < 1e-9) { converged = true; break; }
    currentLL = logLikelihood(X, y, beta);
  }
  if (!converged) throw new Error("IRLS did not converge");

  const etaFinal = X.map(row => Math.max(-30, Math.min(30, matVec([row], beta)[0])));
  const muFinal = etaFinal.map(e => 1 / (1 + Math.exp(-e)));
  const wFinal = muFinal.map(m => m * (1 - m));
  const bread = inverse(xtWx(X, wFinal));

  const groups = new Map();
  clusters.forEach((c, i) => {
    if (!groups.has(c)) groups.set(c, []);
    groups.get(c).push(i);
  });
  const meat = Array.from({ length: p }, () => new Array(p).fill(0));
  for (const positions of groups.values()) {
    const scoreVec = new Array(p).fill(0);
    for (const i of positions) {
      const resid = y[i] - muFinal[i];
      for (let j = 0; j < p; j++) scoreVec[j] += X[i][j] * resid;
    }
    for (let a = 0; a < p; a++) for (let b = 0; b < p; b++) meat[a][b] += scoreVec[a] * scoreVec[b];
  }

  const g = groups.size;
  // covariance = bread @ meat @ bread * (g/(g-1)) * ((n-1)/(n-p))
  function matMul(A, B) {
    const rA = A.length, cA = A[0].length, cB = B[0].length;
    const out = Array.from({ length: rA }, () => new Array(cB).fill(0));
    for (let i = 0; i < rA; i++) for (let k = 0; k < cA; k++) {
      const aik = A[i][k];
      if (aik === 0) continue;
      for (let j = 0; j < cB; j++) out[i][j] += aik * B[k][j];
    }
    return out;
  }
  const scale = (g / (g - 1)) * ((n - 1) / (n - p));
  const bm = matMul(bread, meat);
  const covRaw = matMul(bm, bread);
  const covariance = covRaw.map(row => row.map(v => v * scale));
  const se = covariance.map((row, i) => Math.sqrt(row[i]));

  return { beta, se, covariance, g, n };
}

function normalPValue(z) {
  // Two-sided p-value for a standard-normal z, via the erf-based normal CDF.
  function erf(x) {
    // Abramowitz & Stegun 7.1.26 approximation, ~1.5e-7 max error.
    const sign = x < 0 ? -1 : 1;
    x = Math.abs(x);
    const a1 = 0.254829592, a2 = -0.284496736, a3 = 1.421413741;
    const a4 = -1.453152027, a5 = 1.061405429, pp = 0.3275911;
    const t = 1 / (1 + pp * x);
    const y = 1 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x);
    return sign * y;
  }
  return 2 * (1 - 0.5 * (1 + erf(Math.abs(z) / Math.sqrt(2))));
}

function oddsRatioTable(beta, se, columns) {
  return columns.map((term, i) => ({
    term,
    odds_ratio: Math.exp(beta[i]),
    ci_low: Math.exp(beta[i] - 1.96 * se[i]),
    ci_high: Math.exp(beta[i] + 1.96 * se[i]),
    p_value: normalPValue(beta[i] / se[i]),
  }));
}

if (typeof module !== "undefined") {
  module.exports = { fitClusteredLogit, oddsRatioTable, normalPValue };
}
