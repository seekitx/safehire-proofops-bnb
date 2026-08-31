(() => {
  const agentContainer = document.getElementById("liveAgents");
  const status = document.getElementById("liveMarketStatus");
  const meta = document.getElementById("liveMarketMeta");
  const boundary = document.getElementById("liveMarketBoundary");
  const quotePanel = document.getElementById("liveQuotePanel");
  const quoteTitle = document.getElementById("liveQuoteTitle");
  const quoteState = document.getElementById("liveQuoteState");
  const quoteFacts = document.getElementById("liveQuoteFacts");
  const quoteBoundary = document.getElementById("liveQuoteBoundary");
  const quoteIdentity = document.getElementById("liveQuoteIdentity");
  const continueLiveHire = document.getElementById("continueLiveHire");
  const closeQuote = document.getElementById("closeLiveQuote");
  const intakeForm = document.getElementById("providerIntakeForm");
  const intakeResult = document.getElementById("providerIntakeResult");
  if (!agentContainer || !status || !meta || !boundary || !quotePanel) return;

  const categoryLabels = {
    rebalancing: "Portfolio rebalancing",
    grid_trading: "Grid trading",
    yield_optimisation: "Yield optimisation",
    health_factor_monitoring: "Health factor",
  };

  const escapeHtml = (value) => String(value ?? "").replace(/[&<>'\"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '\"': "&quot;",
  })[character]);

  const safeHttpsUrl = (value) => {
    try {
      const url = new URL(String(value));
      return url.protocol === "https:" ? escapeHtml(url.href) : "#";
    } catch (_error) {
      return "#";
    }
  };

  const renderInputs = (inputs) => Object.entries(inputs || {})
    .map(([name, description]) => `<li><code>${escapeHtml(name)}</code><span>${escapeHtml(description)}</span></li>`)
    .join("");

  const renderAgent = (agent) => {
    const callable = agent.currently_callable === true;
    const signals = agent.market_signals || {};
    const liveInputs = agent.current_capability?.input?.properties;
    const inputs = liveInputs || agent.required_inputs || {};
    return `
      <article class="live-agent-card ${callable ? "reachable" : "unreachable"}">
        <div class="live-card-kicker">
          <span>${escapeHtml(categoryLabels[agent.category] || agent.category)}</span>
          <span class="reachability">${callable ? "A2A REACHABLE" : "A2A UNREACHABLE"}</span>
        </div>
        <h3>${escapeHtml(agent.name)}</h3>
        <p>${escapeHtml(agent.description)}</p>
        <dl>
          <div><dt>ERC-8004 ID</dt><dd>#${escapeHtml(agent.token_id)}</dd></div>
          <div><dt>Quoted price</dt><dd>${escapeHtml(agent.current_capability?.price_display || "0.10 U")}</dd></div>
          <div><dt>Network</dt><dd>BSC mainnet</dd></div>
          <div><dt>SafeHire paid jobs</dt><dd>${escapeHtml(agent.safehire_paid_deliveries || 0)}</dd></div>
        </dl>
        <div class="signal-ledger">
          <div><small>LIVE PROBE</small><strong>${callable ? "REACHABLE" : "UNREACHABLE"}</strong></div>
          <div><small>INDEX HEALTH</small><strong>${escapeHtml(signals.index_a2a_health || "UNKNOWN")}</strong></div>
          <div><small>INDEX SCORE</small><strong>${escapeHtml(signals.total_score ?? "—")}</strong></div>
          <div><small>FEEDBACK</small><strong>${escapeHtml(signals.total_feedbacks ?? 0)}</strong></div>
        </div>
        ${agent.signal_disagreement ? `<p class="signal-warning">${escapeHtml(agent.signal_disagreement)}</p>` : ""}
        <details>
          <summary>Required task input</summary>
          <ul>${renderInputs(inputs)}</ul>
        </details>
        <div class="live-card-actions">
          <button class="quote-button" type="button" data-live-quote="${escapeHtml(agent.skill_id)}">Prepare hire quote</button>
          <a href="${safeHttpsUrl(agent.registry_url)}" target="_blank" rel="noreferrer">8004 identity <span>↗</span></a>
          <a href="${safeHttpsUrl(agent.registration_url)}" target="_blank" rel="noreferrer">Registration tx <span>↗</span></a>
        </div>
        <p class="no-auto-hire">Quote is live. Mainnet funding remains a separate wallet action and is never automatic.</p>
      </article>`;
  };

  const shortAddress = (value) => {
    const text = String(value || "");
    return text.length > 18 ? `${text.slice(0, 10)}…${text.slice(-8)}` : text;
  };

  const prepareQuote = async (skillId, button) => {
    quotePanel.hidden = false;
    quotePanel.classList.add("loading");
    quotePanel.classList.remove("error");
    quoteTitle.textContent = "Contacting the live Agent…";
    quoteState.textContent = "NO TRANSACTION";
    quoteFacts.innerHTML = '<span class="quote-loading">Requesting current ERC-8183 terms…</span>';
    quoteBoundary.textContent = "No wallet has been connected and no token approval has been requested.";
    quoteIdentity.href = "#";
    if (continueLiveHire) continueLiveHire.hidden = true;
    button.disabled = true;
    quotePanel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try {
      const response = await fetch("/api/live-market/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ skill_id: skillId }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      const quote = payload.quote || {};
      quoteTitle.textContent = `${payload.agent?.name || skillId} accepted the request`;
      quoteState.textContent = payload.transaction_sent ? "TRANSACTION SENT" : "QUOTE ONLY · NO TRANSACTION";
      quoteFacts.innerHTML = `
        <div><small>PRICE</small><strong>${escapeHtml(quote.price_display || quote.price)}</strong></div>
        <div><small>NETWORK</small><strong>BSC MAINNET</strong></div>
        <div><small>PROVIDER</small><strong title="${escapeHtml(quote.provider)}">${escapeHtml(shortAddress(quote.provider))}</strong></div>
        <div><small>EST. DELIVERY</small><strong>${escapeHtml(quote.estimated_completion_seconds || "—")} sec</strong></div>`;
      quoteBoundary.textContent = payload.evidence_boundary;
      quoteIdentity.href = safeHttpsUrl(payload.agent?.registration_url);
      if (continueLiveHire) {
        continueLiveHire.href = `/hire-live?skill_id=${encodeURIComponent(skillId)}`;
        continueLiveHire.hidden = false;
      }
    } catch (error) {
      quotePanel.classList.add("error");
      quoteTitle.textContent = "Live quote unavailable";
      quoteState.textContent = "NOT ACTIVATED";
      quoteFacts.innerHTML = `<span class="quote-loading">${escapeHtml(error.message)}</span>`;
      quoteBoundary.textContent = "No transaction was sent. Try again after the external Agent recovers.";
      if (continueLiveHire) continueLiveHire.hidden = true;
    } finally {
      quotePanel.classList.remove("loading");
      button.disabled = false;
    }
  };

  fetch("/api/live-market", { headers: { Accept: "application/json" } })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .then((payload) => {
      const agents = Array.isArray(payload.agents) ? payload.agents : [];
      agentContainer.innerHTML = agents.map(renderAgent).join("");
      const callableCount = agents.filter((agent) => agent.currently_callable).length;
      status.classList.toggle("offline", payload.endpoint_reachable !== true);
      status.querySelector("strong").textContent = payload.endpoint_reachable
        ? `${callableCount}/${agents.length} skills callable now`
        : "Registration snapshot loaded; A2A is offline";
      meta.textContent = `Checked ${new Date(payload.observed_at).toLocaleString()} · ${payload.operator_count || 0} independent operator(s) · read-only`;
      boundary.textContent = payload.trust_boundary;
      agentContainer.querySelectorAll("[data-live-quote]").forEach((button) => {
        button.addEventListener("click", () => prepareQuote(button.dataset.liveQuote, button));
      });
    })
    .catch((error) => {
      status.classList.add("offline");
      status.querySelector("strong").textContent = "Live-market evidence unavailable";
      meta.textContent = error.message;
      agentContainer.innerHTML = '<p class="live-market-error">The page refused to replace missing live evidence with demo data.</p>';
    });

  closeQuote?.addEventListener("click", () => {
    quotePanel.hidden = true;
  });

  intakeForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const button = intakeForm.querySelector("button");
    button.disabled = true;
    button.textContent = "Checking official index…";
    intakeResult.hidden = false;
    intakeResult.innerHTML = "<p>Building a read-only listing dossier…</p>";
    try {
      const response = await fetch("/api/providers/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({
          chain_id: Number(document.getElementById("providerChain").value),
          token_id: Number(document.getElementById("providerTokenId").value),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      intakeResult.innerHTML = `
        <div class="intake-head"><strong>${escapeHtml(payload.agent?.name || `Agent #${payload.token_id}`)}</strong><span>${payload.eligible_for_review ? "READY FOR CURATOR REVIEW" : "BLOCKING CHECKS FAILED"}</span></div>
        <ul>${(payload.checks || []).map((check) => `<li class="${check.passed ? "passed" : "failed"}"><b>${check.passed ? "PASS" : "FAIL"}</b><span>${escapeHtml(check.detail)}</span></li>`).join("")}</ul>
        <p>${escapeHtml(payload.trust_boundary)}</p>`;
    } catch (error) {
      intakeResult.innerHTML = `<p class="intake-error">No listing was created: ${escapeHtml(error.message)}</p>`;
    } finally {
      button.disabled = false;
      button.textContent = "Preview listing dossier";
    }
  });
})();
