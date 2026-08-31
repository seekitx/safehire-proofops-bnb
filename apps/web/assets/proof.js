const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function short(value, head = 10, tail = 8) {
  const text = String(value ?? "");
  return text.length > head + tail + 2 ? `${text.slice(0, head)}…${text.slice(-tail)}` : text;
}

function safeHttpsUrl(value) {
  try {
    const url = new URL(String(value));
    return url.protocol === "https:" ? url.href : "#";
  } catch (_error) {
    return "#";
  }
}

function titleForStep(step) {
  return {
    create_job: "Job created",
    register_job: "Policy bound",
    set_budget: "Budget fixed",
    approve_u: "0.1 U approved",
    fund_job: "Escrow funded",
    submit_delivery: "Delivery submitted",
    settle_job: "Provider paid",
  }[step] || String(step).replaceAll("_", " ");
}

async function loadProof() {
  const response = await fetch("/api/public-proof", { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`Evidence API returned HTTP ${response.status}`);
  const proof = await response.json();
  const job = proof.erc8183;

  byId("heroJobId").textContent = `#${job.job_id}`;
  byId("heroJobStatus").textContent = job.status;
  byId("receiptCount").textContent = String(job.transactions.length);
  byId("agentId").textContent = `#${proof.erc8004.agent_id}`;
  byId("contractCount").textContent = String(proof.contracts.length);
  byId("reviewWindow").textContent = `${Math.round(job.dispute_window_seconds / 60)} min`;
  byId("deliverableLink").href = safeHttpsUrl(job.deliverable_url);

  byId("jobTimeline").innerHTML = job.transactions.map((transaction, index) => `
    <a class="timeline-row" href="${escapeHtml(safeHttpsUrl(transaction.explorer_url))}" target="_blank" rel="noreferrer">
      <span class="timeline-index">${String(index + 1).padStart(2, "0")}</span>
      <span><strong>${escapeHtml(titleForStep(transaction.step))}</strong><small>Block ${escapeHtml(transaction.block_number)} · ${escapeHtml(transaction.block_timestamp)}</small></span>
      <code>${escapeHtml(short(transaction.tx_hash))}</code>
      <b>CONFIRMED ↗</b>
    </a>`).join("");

  byId("identityTitle").textContent = `Agent #${proof.erc8004.agent_id}`;
  byId("identityReadback").textContent = proof.erc8004.readback_verified
    ? "Owner, Agent wallet and public URI independently read back from BSC Testnet."
    : "Identity readback evidence is incomplete.";
  byId("registrationLink").href = safeHttpsUrl(proof.erc8004.registration_url);
  byId("uriLink").href = safeHttpsUrl(proof.erc8004.uri_update_url);

  const runtime = proof.agent_studio;
  const runtimeExpiresAt = runtime.expires_at ? new Date(runtime.expires_at) : null;
  const runtimeExpired = runtimeExpiresAt instanceof Date
    && Number.isFinite(runtimeExpiresAt.getTime())
    && runtimeExpiresAt.getTime() <= Date.now();
  const historicalExpiry = runtime.historical_trial?.expires_at
    ? new Date(runtime.historical_trial.expires_at)
    : null;
  const historicalNote = historicalExpiry instanceof Date && Number.isFinite(historicalExpiry.getTime())
    ? ` The original BNB Agent Studio signing trial is preserved as historical evidence and expired ${historicalExpiry.toLocaleString()}.`
    : "";
  byId("runtimeStatus").textContent = runtimeExpired
    ? "EXPIRED"
    : String(runtime.status).toLowerCase() === "running" ? "LIVE" : String(runtime.status).toUpperCase();
  byId("runtimeExpiry").textContent = runtimeExpired
    ? `This public runtime expired ${runtimeExpiresAt.toLocaleString()}.${historicalNote}`
    : `The public read-only Agent Card and A2A preview bridge run on ${String(runtime.provider || "durable hosting").toUpperCase()} without a trial expiry.${historicalNote}`;
  byId("runtimeCard").classList.toggle("danger", runtimeExpired);
  byId("agentCardLink").href = safeHttpsUrl(proof.agent_studio.endpoint);
  byId("a2aLink").href = safeHttpsUrl(proof.agent_studio.a2a_url);

  byId("contractGrid").innerHTML = proof.contracts.map((contract) => `
    <article class="contract-card">
      <p>${escapeHtml(contract.name)}</p>
      <strong>${escapeHtml(short(contract.address, 8, 8))}</strong>
      <code>${escapeHtml(short(contract.tx_hash))}</code>
      <div class="link-row"><a href="${escapeHtml(safeHttpsUrl(contract.address_url))}" target="_blank" rel="noreferrer">Contract ↗</a><a href="${escapeHtml(safeHttpsUrl(contract.transaction_url))}" target="_blank" rel="noreferrer">Deploy tx ↗</a></div>
    </article>`).join("");

  const pancake = proof.pancakeswap_v3;
  byId("routeImprovement").textContent = `${Number(pancake.decision.improvement_usdt).toFixed(4)} USDT`;
  byId("routeMeta").textContent = `${pancake.input.amount_in_display} · block ${pancake.observed_block} · ${Number(pancake.decision.improvement_bps).toFixed(4)} bps over 0.05%`;
  byId("pancakeSource").href = safeHttpsUrl(pancake.source_url);
  byId("routeQuotes").innerHTML = pancake.quotes.map((quote) => {
    const selected = String(quote.pool_address).toLowerCase() === String(pancake.decision.selected_pool).toLowerCase();
    return `
      <a class="route-row ${selected ? "selected" : ""}" href="${escapeHtml(safeHttpsUrl(quote.pool_url))}" target="_blank" rel="noreferrer">
        <span>${escapeHtml(quote.fee_percent)}% fee</span>
        <strong>${Number(quote.amount_out_usdt).toFixed(6)} USDT</strong>
        <small>${selected ? "SELECTED" : `${escapeHtml(quote.initialized_ticks_crossed)} tick crossed`} ↗</small>
      </a>`;
  }).join("");
  byId("routeBenefit").textContent = pancake.measurable_benefit;
  byId("routeRisk").textContent = pancake.risk_boundary;

  byId("verifiedClaim").textContent = proof.honesty_boundary.verified;
  byId("unclaimedClaim").textContent = proof.honesty_boundary.not_claimed;
}

loadProof().catch((error) => {
  byId("jobTimeline").innerHTML = `<p class="load-error">Could not load public evidence: ${escapeHtml(error.message)}</p>`;
});
