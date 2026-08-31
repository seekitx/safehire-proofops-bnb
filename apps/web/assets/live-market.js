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
  const closeQuote = document.getElementById("closeLiveQuote");
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
          <div><dt>Operator</dt><dd>External</dd></div>
        </dl>
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
    } catch (error) {
      quotePanel.classList.add("error");
      quoteTitle.textContent = "Live quote unavailable";
      quoteState.textContent = "NOT ACTIVATED";
      quoteFacts.innerHTML = `<span class="quote-loading">${escapeHtml(error.message)}</span>`;
      quoteBoundary.textContent = "No transaction was sent. Try again after the external Agent recovers.";
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
      meta.textContent = `Checked ${new Date(payload.observed_at).toLocaleString()} · read-only discovery`;
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
})();
