// Recomputes the borough-odds finding live, against the current NYC Open
// Data feed. Gated behind live-check.js's completeness check passing --
// running a regression against a feed already known to be short would risk
// the exact silent, wrong-looking result this project fixed once already
// (see README.md's "Reproducing this"). Uses pairing.js for the same
// pairing/design-matrix pipeline regression.py runs, and regression.js for
// the same clustered-logit fit -- both checked against the trusted Python
// baseline in tests/, not trusted fresh here.
(() => {
  const API_ENDPOINT = "https://data.cityofnewyork.us/resource/43nn-pn8j.json";
  const PAGE_SIZE = 50000;
  const PAGE_TIMEOUT_MS = 30000;

  // From outputs/reinspection_model_results.txt -- the last confirmed,
  // published fit. ALPHA is the same conventional 0.05 threshold index.html
  // uses when it says a term "misses conventional significance."
  const BASELINE = {
    n: 14414,
    g: 11095,
    terms: [
      { column: "borough_Bronx", label: "Bronx", odds_ratio: 1.124, p_value: 0.110 },
      { column: "borough_Brooklyn", label: "Brooklyn", odds_ratio: 0.979, p_value: 0.686 },
      { column: "borough_Queens", label: "Queens", odds_ratio: 1.107, p_value: 0.056 },
      { column: "borough_Staten Island", label: "Staten Island", odds_ratio: 0.864, p_value: 0.164 },
    ],
  };
  const ALPHA = 0.05;

  const section = document.getElementById("recompute-section");
  if (!section) return;

  function renderPrompt() {
    section.innerHTML = `
      <div class="chart-block">
        <p style="margin:0 0 12px;">
          <strong>Recompute the borough-odds finding against today's data?</strong>
          This pulls the complete live table (roughly 295,000 rows, paginated)
          into your browser and re-fits the same restaurant-clustered logistic
          model shown on the homepage. It can take a minute or more and uses
          real bandwidth.
        </p>
        <button type="button" id="recompute-start">Recompute now</button>
      </div>
    `;
    document.getElementById("recompute-start").addEventListener("click", runRecompute);
  }

  function renderProgress(rowsSoFar, page) {
    section.innerHTML = `
      <div class="chart-block">
        <p>Pulling the live table&hellip; ${rowsSoFar.toLocaleString()} rows so far (page ${page}).</p>
      </div>
    `;
  }

  function renderFitting(rowCount) {
    section.innerHTML = `
      <div class="chart-block">
        <p>Pairing ${rowCount.toLocaleString()} raw rows into initial&rarr;re-inspection visits and fitting the clustered logistic model&hellip;</p>
      </div>
    `;
  }

  function renderError(message) {
    section.innerHTML = `
      <div class="chart-block">
        <p><strong>Recompute did not finish.</strong></p>
        <p class="note" style="margin:8px 0 12px;">${message} No live result to show -- the homepage's published numbers are unaffected either way.</p>
        <button type="button" id="recompute-retry">Try again</button>
      </div>
    `;
    document.getElementById("recompute-retry").addEventListener("click", runRecompute);
  }

  function fmt(n, digits = 3) {
    return n.toFixed(digits);
  }

  function renderResult({ n, g, table }) {
    const rows = BASELINE.terms.map((base) => {
      const live = table.find((r) => r.term === base.column);
      const liveSignificant = live.p_value < ALPHA;
      const baseSignificant = base.p_value < ALPHA;
      const crossed = liveSignificant !== baseSignificant;
      return { base, live, crossed };
    });

    const anyCrossed = rows.some((r) => r.crossed);

    const tableRows = rows.map(({ base, live, crossed }) => `
      <tr${crossed ? ' style="background:color-mix(in srgb, var(--viz-series-4) 12%, transparent);"' : ""}>
        <td>${base.label}${crossed ? ' <strong style="color:var(--viz-series-4);">&#9650; crossed</strong>' : ""}</td>
        <td class="num">${fmt(base.odds_ratio)}</td>
        <td class="num">${fmt(live.odds_ratio)}</td>
        <td class="num">${fmt(base.p_value)}</td>
        <td class="num">${fmt(live.p_value)}</td>
      </tr>
    `).join("");

    section.innerHTML = `
      <div class="chart-block">
        <p style="margin:0 0 4px;"><strong>Live recompute finished.</strong></p>
        <p class="note" style="margin:0 0 16px;">
          ${n.toLocaleString()} paired visits from ${g.toLocaleString()} restaurants in today's
          feed (published baseline: ${BASELINE.n.toLocaleString()} visits, ${BASELINE.g.toLocaleString()}
          restaurants). This reports what today's data shows -- it is not, on its own, a
          claim that the underlying borough effect has grown, shrunk, or reversed; a small
          sample continuing to sit near the conventional 0.05 significance line can cross it
          either way from noise alone (see index.html's own multiple-comparisons caution).
          ${anyCrossed
            ? "At least one borough below crossed that line since the published baseline -- worth a second look, not a new headline on its own."
            : "No borough crossed the conventional 0.05 significance line relative to the published baseline."}
        </p>
        <div style="overflow-x:auto;">
          <table class="data-table">
            <thead>
              <tr><th>Borough</th><th class="num">Baseline OR</th><th class="num">Live OR</th><th class="num">Baseline p</th><th class="num">Live p</th></tr>
            </thead>
            <tbody>${tableRows}</tbody>
          </table>
        </div>
        <button type="button" id="recompute-again" style="margin-top:12px;">Recompute again</button>
      </div>
    `;
    document.getElementById("recompute-again").addEventListener("click", runRecompute);
  }

  async function fetchAllRows(onProgress) {
    let allRows = [];
    let offset = 0;
    let page = 1;
    while (true) {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), PAGE_TIMEOUT_MS);
      const params = new URLSearchParams({
        "$limit": String(PAGE_SIZE),
        "$offset": String(offset),
        // Stable total order so paginated $offset requests neither skip nor
        // duplicate rows within this pull -- matches download_data.py.
        "$order": "camis, inspection_date, violation_code",
      });
      let response;
      try {
        response = await fetch(`${API_ENDPOINT}?${params}`, { signal: controller.signal });
      } catch (error) {
        clearTimeout(timeoutId);
        if (error.name === "AbortError") throw new Error(`Page ${page} took too long and was stopped.`);
        throw new Error(`Page ${page} failed before it reached the feed.`);
      }
      clearTimeout(timeoutId);
      if (!response.ok) throw new Error(`Page ${page} responded with status ${response.status}.`);
      const rows = await response.json();
      allRows = allRows.concat(rows);
      onProgress(allRows.length, page);
      if (rows.length < PAGE_SIZE) break;
      offset += PAGE_SIZE;
      page += 1;
    }
    return allRows;
  }

  async function runRecompute() {
    renderProgress(0, 1);
    try {
      const raw = await fetchAllRows(renderProgress);
      renderFitting(raw.length);
      // Yield a frame so the fitting message actually paints before the
      // (synchronous, CPU-bound) pairing and fit work runs.
      await new Promise((resolve) => setTimeout(resolve, 0));

      const df = window.buildPairedDataset(raw);
      if (df.length === 0) throw new Error("Pairing produced zero eligible rows -- something is wrong with today's pull, not the model.");
      const { X, columns } = window.designMatrix(df);
      const y = df.map((r) => r.b_or_c);
      const clusters = df.map((r) => r.camis);

      let fit;
      try {
        fit = window.fitClusteredLogit(X, y, clusters);
      } catch (error) {
        throw new Error("The model did not converge against today's data. This can happen with a genuinely unstable fit, not only a bad pull.");
      }
      const table = window.oddsRatioTable(fit.beta, fit.se, columns);
      renderResult({ n: fit.n, g: fit.g, table });
    } catch (error) {
      renderError(error.message || "An unexpected error stopped the recompute.");
    }
  }

  document.addEventListener("livecheck:complete", () => renderPrompt());
})();
