// Checks the live NYC Open Data feed's row count before this tool ever
// recomputes anything against it. This is the completeness hard-stop
// described in README.md: an earlier version of this project pulled an
// unsorted, paginated slice that silently stopped early and produced a
// confident, wrong-looking result. This check exists so a partial pull
// blocks the regression instead of quietly feeding it.
(() => {
  const API_ENDPOINT = "https://data.cityofnewyork.us/resource/43nn-pn8j.json";

  // The row count of the last snapshot this project fully verified and
  // published (see NOTES.md / README.md). Not a fixed target the live
  // feed must match exactly -- the feed only grows over time, so "at or
  // above this" is complete; "below this" means something came back
  // short, either the feed itself or this fetch.
  const LAST_CONFIRMED_COUNT = 295048;

  // Socrata occasionally takes a while to answer a count query under
  // load; past this, treat the request as failed rather than waiting
  // indefinitely with no signal.
  const REQUEST_TIMEOUT_MS = 15000;

  const statusEl = document.getElementById("live-check-status");

  function renderLoading() {
    statusEl.innerHTML = `<p>Checking the live feed&hellip; this confirms row-count completeness before anything else runs.</p>`;
  }

  function renderComplete(liveCount) {
    statusEl.innerHTML = `
      <p><strong>The live feed currently holds ${liveCount.toLocaleString()} rows</strong> — at or above the last confirmed complete population (${LAST_CONFIRMED_COUNT.toLocaleString()}).</p>
      <p class="note">Completeness check passed: the feed looks whole enough to compute from safely. That is not the same claim as "the borough-gap finding holds" -- this page does not show that finding on its own, only whether the data underneath it would currently be trustworthy to recompute against. See below to run that recompute.</p>
    `;
    document.dispatchEvent(new CustomEvent("livecheck:complete", { detail: { liveCount } }));
  }

  function renderIncomplete(liveCount) {
    statusEl.innerHTML = `
      <p><strong>The live feed returned ${liveCount.toLocaleString()} rows</strong> — below the last confirmed complete population (${LAST_CONFIRMED_COUNT.toLocaleString()}).</p>
      <p class="note">No verdict shown. ${LAST_CONFIRMED_COUNT.toLocaleString()} is a fixed point-in-time reference, not a permanent floor the feed must always clear -- a small, temporary dip below it can happen from a legitimate correction to the source data, not only from a broken pull. Either way, running a regression against a count this low risks the same silent, wrong-looking result this project already fixed once, so none runs until the count recovers. Falling back to the last confirmed result: see <a href="outputs/reinspection_model_results.txt">outputs/reinspection_model_results.txt</a>.</p>
    `;
  }

  function renderFailed(reason) {
    statusEl.innerHTML = `
      <p><strong>Unable to confirm the live feed right now.</strong></p>
      <p class="note">${reason} No verdict shown. Falling back to the last confirmed result: see <a href="outputs/reinspection_model_results.txt">outputs/reinspection_model_results.txt</a>. <button type="button" id="live-check-retry">Try again</button></p>
    `;
    document.getElementById("live-check-retry").addEventListener("click", runCheck);
  }

  function runCheck() {
    renderLoading();

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

    const params = new URLSearchParams({ "$select": "count(*) as row_count" });

    fetch(`${API_ENDPOINT}?${params}`, { signal: controller.signal })
      .then((response) => {
        clearTimeout(timeoutId);
        if (!response.ok) {
          throw new Error(`the feed responded with status ${response.status}.`);
        }
        return response.json();
      })
      .then((rows) => {
        // A malformed or empty response here is the same ambiguous shape
        // covered in this project's own design notes: a request that
        // "succeeded" but did not actually answer the question. Treated
        // as failed, not as an incomplete count of zero, since zero rows
        // is not a real possible state for this feed.
        const liveCount = rows && rows[0] && Number(rows[0].row_count);
        if (!liveCount || Number.isNaN(liveCount)) {
          renderFailed("The feed returned a response with no usable row count.");
          return;
        }
        if (liveCount < LAST_CONFIRMED_COUNT) {
          renderIncomplete(liveCount);
        } else {
          renderComplete(liveCount);
        }
      })
      .catch((error) => {
        clearTimeout(timeoutId);
        const reason = error.name === "AbortError"
          ? "The request took too long and was stopped."
          : "The request failed before it reached the feed.";
        renderFailed(reason);
      });
  }

  runCheck();
})();
