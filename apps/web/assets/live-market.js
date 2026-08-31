(() => {
  const agentContainer = document.getElementById("liveAgents");
  const status = document.getElementById("liveMarketStatus");
  const meta = document.getElementById("liveMarketMeta");
  const boundary = document.getElementById("liveMarketBoundary");
  if (!agentContainer || !status || !meta || !boundary) return;

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
          <a href="${safeHttpsUrl(agent.registry_url)}" target="_blank" rel="noreferrer">8004 identity <span>↗</span></a>
          <a href="${safeHttpsUrl(agent.registration_url)}" target="_blank" rel="noreferrer">Registration tx <span>↗</span></a>
        </div>
        <p class="no-auto-hire">SafeHire will not fund or sign a mainnet job from this discovery card.</p>
      </article>`;
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
    })
    .catch((error) => {
      status.classList.add("offline");
      status.querySelector("strong").textContent = "Live-market evidence unavailable";
      meta.textContent = error.message;
      agentContainer.innerHTML = '<p class="live-market-error">The page refused to replace missing live evidence with demo data.</p>';
    });
})();
