const CATEGORY_LABELS = {
  all: "All agents",
  rebalancing: "LP rebalancing",
  grid_trading: "Grid trading",
  yield_optimisation: "Yield optimisation",
  health_factor_monitoring: "Health factor",
};

const state = {
  agents: [],
  selected: new Set(),
  category: "all",
  activeAgent: null,
  activeCard: null,
  runtime: null,
  wallet: sessionStorage.getItem("safehire_wallet"),
  sessionToken: sessionStorage.getItem("safehire_session"),
  task: null,
  policy: null,
  agentResult: null,
};

const $ = (selector) => document.querySelector(selector);
const byId = (id) => document.getElementById(id);

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function short(value, head = 8, tail = 6) {
  const text = String(value ?? "");
  return text.length > head + tail + 2
    ? `${text.slice(0, head)}…${text.slice(-tail)}`
    : text;
}

function requestId(prefix) {
  const suffix = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`;
  return `${prefix}-${suffix}`;
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    "X-Request-ID": requestId("web"),
    ...(options.headers || {}),
  };
  if (state.sessionToken && !headers.Authorization) {
    headers.Authorization = `Bearer ${state.sessionToken}`;
  }
  const response = await fetch(path, { ...options, headers });
  let body = {};
  try {
    body = await response.json();
  } catch {
    body = { message: await response.text() };
  }
  if (!response.ok) {
    const message = body.detail || body.message || body.error || `HTTP ${response.status}`;
    if (response.status === 401) clearWalletSession();
    throw new Error(message);
  }
  return body;
}

let toastTimer;
function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 4200);
}

function setStatus(id, text, kind = "") {
  const element = byId(id);
  element.textContent = text;
  element.className = kind;
}

function updateWalletButton() {
  const button = byId("walletButton");
  const owner = byId("ownerAddress");
  if (state.wallet && state.sessionToken) {
    button.textContent = short(state.wallet);
    owner.value = state.wallet;
  } else {
    button.textContent = "Connect wallet";
    owner.value = "";
  }
  updateHireAvailability();
}

function clearWalletSession() {
  state.wallet = null;
  state.sessionToken = null;
  sessionStorage.removeItem("safehire_wallet");
  sessionStorage.removeItem("safehire_session");
  updateWalletButton();
}

function symbolFor(agent) {
  return agent.name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
}

function agentCard(agent) {
  const proof = agent.agent_proof;
  const categoryMetrics = Object.entries(agent.metrics.category_metrics).slice(0, 3);
  const sourceLabels = proof.source_labels || [];
  const selected = state.selected.has(agent.agent_id);
  return `
    <article class="agent-card ${selected ? "selected" : ""}" data-agent-card="${escapeHtml(agent.agent_id)}">
      <div class="agent-top">
        <div>
          <div class="eyebrow">${escapeHtml(CATEGORY_LABELS[agent.category] || agent.category)}</div>
          <h3>${escapeHtml(agent.name)}</h3>
          <p class="muted">${escapeHtml(agent.description)}</p>
        </div>
        <div class="score"><div><strong>${escapeHtml(proof.final_score)}</strong><small>AGENTPROOF</small></div></div>
      </div>
      <div class="badges">
        <span class="badge ${agent.live_bsc ? "" : "fixture"}">${agent.live_bsc ? "LIVE BSC" : "DEMO ONLY"}</span>
        <span class="badge">EVIDENCE CAP ${escapeHtml(proof.evidence_cap)}</span>
        ${sourceLabels.map((source) => `<span class="badge ${source === "demo_fixture" ? "fixture" : ""}">${escapeHtml(source)}</span>`).join("")}
      </div>
      <div class="metric-grid">
        ${categoryMetrics.map(([key, value]) => `<div class="metric"><label title="${escapeHtml(key)}">${escapeHtml(key.replaceAll("_", " "))}</label><strong>${escapeHtml(value)}</strong></div>`).join("")}
      </div>
      <div class="card-actions">
        <label class="compare-check"><input type="checkbox" data-compare="${escapeHtml(agent.agent_id)}" ${selected ? "checked" : ""}/> Compare</label>
        <button class="text-button" type="button" data-hire="${escapeHtml(agent.agent_id)}">Inspect &amp; hire →</button>
      </div>
    </article>`;
}

function renderCategories() {
  const categories = ["all", ...new Set(state.agents.map((agent) => agent.category))];
  byId("categories").innerHTML = categories
    .map((category) => `<button class="tab ${category === state.category ? "active" : ""}" type="button" role="tab" data-category="${escapeHtml(category)}">${escapeHtml(CATEGORY_LABELS[category] || category)}</button>`)
    .join("");
}

function renderAgents() {
  const agents = state.category === "all"
    ? state.agents
    : state.agents.filter((agent) => agent.category === state.category);
  byId("agents").innerHTML = agents.length
    ? agents.map(agentCard).join("")
    : "<p>No agent is available in this category.</p>";
  byId("compareCount").textContent = String(state.selected.size);
  byId("compareButton").disabled = state.selected.size < 2 || state.selected.size > 3;
  byId("compareBar").classList.toggle("hidden", state.selected.size === 0);
}

function updateSteps(step) {
  [...byId("steps").children].forEach((item, index) => {
    item.classList.toggle("done", index + 1 < step);
    item.classList.toggle("active", index + 1 === step);
  });
}

function updateHireAvailability() {
  const selected = Boolean(state.activeAgent && state.activeCard);
  byId("previewButton").disabled = !selected;
  byId("taskInput").disabled = !selected;
  byId("hireButton").disabled = !(selected && state.wallet && state.sessionToken);
  if (!selected) updateSteps(1);
  else if (!(state.wallet && state.sessionToken)) updateSteps(2);
  else updateSteps(3);
}

async function selectAgent(agentId) {
  try {
    const [agent, card] = await Promise.all([
      api(`/api/agents/${encodeURIComponent(agentId)}`),
      api(`/agents/${encodeURIComponent(agentId)}`),
    ]);
    state.activeAgent = agent;
    state.activeCard = card;
    state.task = null;
    state.policy = null;
    state.agentResult = null;
    byId("workflowPanel").classList.add("hidden");
    byId("consoleAgent").innerHTML = `
      <span class="agent-symbol">${escapeHtml(symbolFor(agent))}</span>
      <div><small>Selected agent</small><strong>${escapeHtml(agent.name)}</strong><p>${escapeHtml(agent.description)}</p></div>
      <span class="proof-pill">Proof ${escapeHtml(agent.agent_proof.final_score)} / cap ${escapeHtml(agent.agent_proof.evidence_cap)}</span>`;
    byId("taskInput").value = JSON.stringify(card.example_input, null, 2);
    byId("allowedTarget").value = agent.contract_address || agent.endpoint;
    byId("allowedMethod").value = "invoke";
    updateHireAvailability();
    byId("hire-console").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    toast(`Could not load agent: ${error.message}`, true);
  }
}

function parseTaskInput() {
  try {
    const value = JSON.parse(byId("taskInput").value);
    if (!value || Array.isArray(value) || typeof value !== "object") {
      throw new Error("Task input must be a JSON object.");
    }
    return value;
  } catch (error) {
    throw new Error(`Invalid task JSON: ${error.message}`);
  }
}

function renderWorkflow() {
  if (!state.task || !state.policy) return;
  const result = state.agentResult || state.task.simulation || {};
  const receipt = state.task.receipt;
  const taskState = state.task.state;
  byId("workflowPanel").classList.remove("hidden");
  byId("taskIdentifier").textContent = state.task.task_id;
  byId("taskState").textContent = taskState.replaceAll("_", " ").toUpperCase();
  byId("decisionValue").textContent = result.action || receipt?.result?.status || "—";
  byId("confidenceValue").textContent = result.confidence == null ? "—" : `${Math.round(Number(result.confidence) * 100)}%`;
  byId("expiryValue").textContent = new Date(state.policy.expires_at).toLocaleString();
  byId("sourceValue").textContent = receipt?.source || (result.source_labels || []).join(", ") || "caller_supplied";
  byId("taskResult").textContent = JSON.stringify({ task: state.task, policy: state.policy, agent_result: result }, null, 2);
  byId("approveButton").disabled = taskState !== "approval_required";
  byId("executeButton").disabled = taskState !== "approved";
  byId("revokeButton").disabled = state.policy.revoked || ["succeeded", "failed", "revoked"].includes(taskState);
  byId("executionNote").textContent = receipt?.source === "demo_fixture"
    ? "This receipt is a labeled demo fixture, not a BSC transaction. It cannot satisfy the submission gate."
    : state.runtime?.execution_mode === "demo"
      ? "Demo receipts are visibly labeled and never count as live BSC evidence."
      : "Onchain mode calls the deployed agent endpoint only after approval and the deterministic risk gate.";
  updateSteps(["succeeded", "failed", "revoked"].includes(taskState) ? 4 : 3);
}

async function previewAgent() {
  if (!state.activeAgent) return;
  try {
    const input = parseTaskInput();
    state.agentResult = await api(`/api/agents/${encodeURIComponent(state.activeAgent.agent_id)}/invoke`, {
      method: "POST",
      body: JSON.stringify({ input }),
    });
    byId("workflowPanel").classList.remove("hidden");
    byId("taskIdentifier").textContent = "PREVIEW ONLY";
    byId("taskState").textContent = "NOT HIRED";
    byId("decisionValue").textContent = state.agentResult.action;
    byId("confidenceValue").textContent = `${Math.round(state.agentResult.confidence * 100)}%`;
    byId("expiryValue").textContent = "No permission created";
    byId("sourceValue").textContent = state.agentResult.source_labels.join(", ");
    byId("taskResult").textContent = JSON.stringify(state.agentResult, null, 2);
    byId("approveButton").disabled = true;
    byId("executeButton").disabled = true;
    byId("revokeButton").disabled = true;
    toast("Preview completed. No permission or transaction was created.");
  } catch (error) {
    toast(error.message, true);
  }
}

async function ensureBscTestnet() {
  const chainId = await globalThis.ethereum.request({ method: "eth_chainId" });
  if (chainId === "0x61") return;
  try {
    await globalThis.ethereum.request({
      method: "wallet_switchEthereumChain",
      params: [{ chainId: "0x61" }],
    });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await globalThis.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: "0x61",
        chainName: "BNB Smart Chain Testnet",
        nativeCurrency: { name: "tBNB", symbol: "tBNB", decimals: 18 },
        rpcUrls: ["https://data-seed-prebsc-1-s1.bnbchain.org:8545"],
        blockExplorerUrls: ["https://testnet.bscscan.com"],
      }],
    });
  }
}

async function connectWallet() {
  if (!globalThis.ethereum) {
    toast("No browser wallet found. Install MetaMask or another EVM wallet, then reload.", true);
    return;
  }
  try {
    const accounts = await globalThis.ethereum.request({ method: "eth_requestAccounts" });
    const owner = accounts?.[0];
    if (!owner) throw new Error("The wallet did not return an account.");
    await ensureBscTestnet();
    const challenge = await api("/api/auth/challenge", {
      method: "POST",
      body: JSON.stringify({ owner }),
    });
    const signature = await globalThis.ethereum.request({
      method: "personal_sign",
      params: [challenge.message, owner],
    });
    const session = await api("/api/auth/verify", {
      method: "POST",
      body: JSON.stringify({ owner, message: challenge.message, signature }),
    });
    state.wallet = session.owner;
    state.sessionToken = session.session_token;
    sessionStorage.setItem("safehire_wallet", state.wallet);
    sessionStorage.setItem("safehire_session", state.sessionToken);
    updateWalletButton();
    updateSteps(state.activeAgent ? 3 : 1);
    toast("Wallet verified. This sign-in signature is not a blockchain transaction.");
  } catch (error) {
    toast(`Wallet connection stopped: ${error.message}`, true);
  }
}

function positiveNumber(id) {
  const value = Number(byId(id).value);
  if (!Number.isFinite(value) || value <= 0) throw new Error(`${id} must be greater than zero.`);
  return value;
}

async function hireAgent() {
  if (!state.activeAgent || !state.wallet || !state.sessionToken) {
    toast("Select an agent and connect your wallet first.", true);
    return;
  }
  try {
    const request = parseTaskInput();
    const allowedTarget = byId("allowedTarget").value.trim();
    const allowedMethod = byId("allowedMethod").value.trim();
    if (!allowedTarget || !allowedMethod) throw new Error("Allowed target and method are required.");
    const response = await api(`/api/agents/${encodeURIComponent(state.activeAgent.agent_id)}/hire`, {
      method: "POST",
      body: JSON.stringify({
        owner: state.wallet,
        chain_id: 97,
        allowed_targets: [allowedTarget],
        allowed_methods: [allowedMethod],
        max_value_usd: positiveNumber("maxValue"),
        daily_value_usd: positiveNumber("dailyValue"),
        max_slippage_bps: Number(byId("slippage").value),
        ttl_minutes: Number(byId("ttl").value),
        request,
        idempotency_key: requestId("hire"),
      }),
    });
    state.policy = response.policy;
    state.task = response.task;
    state.agentResult = response.agent_result;
    renderWorkflow();
    toast("Permission and task created. Execution still needs your separate approval.");
  } catch (error) {
    toast(`Hire failed: ${error.message}`, true);
  }
}

async function approveTask() {
  try {
    state.task = await api(`/api/tasks/${encodeURIComponent(state.task.task_id)}/approve`, { method: "POST" });
    renderWorkflow();
    toast("Task approved. The deterministic permission gate will run again on execution.");
  } catch (error) {
    toast(`Approval failed: ${error.message}`, true);
  }
}

async function executeTask() {
  try {
    const demo = state.runtime?.execution_mode === "demo";
    state.task = await api(`/api/tasks/${encodeURIComponent(state.task.task_id)}/execute`, {
      method: "POST",
      body: JSON.stringify({
        idempotency_key: requestId("execute"),
        chain_id: 97,
        target: state.policy.allowed_targets[0],
        method: state.policy.allowed_methods[0],
        value_usd: positiveNumber("maxValue"),
        slippage_bps: Number(byId("slippage").value),
        mode: demo ? "demo" : "bsc_testnet",
        source: demo ? "demo_fixture" : "testnet_evidence",
        metadata: { initiated_by: "safehire_web" },
      }),
    });
    renderWorkflow();
    toast(demo
      ? "Demo receipt created and clearly labeled. No blockchain transaction was sent."
      : "Execution returned. Check the receipt and BscScan transaction before accepting it.");
  } catch (error) {
    toast(`Execution failed: ${error.message}`, true);
  }
}

async function revokePermission() {
  try {
    state.policy = await api(`/api/permissions/${encodeURIComponent(state.policy.policy_id)}/revoke`, { method: "POST" });
    if (!["succeeded", "failed", "revoked"].includes(state.task.state)) {
      state.task = await api(`/api/tasks/${encodeURIComponent(state.task.task_id)}/revoke`, { method: "POST" });
    }
    renderWorkflow();
    toast("Permission revoked. Future execution attempts will fail closed.");
  } catch (error) {
    toast(`Revoke failed: ${error.message}`, true);
  }
}

async function compareSelected() {
  try {
    const result = await api("/api/compare", {
      method: "POST",
      body: JSON.stringify({ agent_ids: [...state.selected] }),
    });
    byId("comparison").innerHTML = result.agents.map((agent) => `
      <article class="compare-card">
        <div class="eyebrow">${escapeHtml(CATEGORY_LABELS[agent.category] || agent.category)}</div>
        <h3>${escapeHtml(agent.name)}</h3>
        <p class="muted">Proof ${escapeHtml(agent.agent_proof.final_score)} · evidence cap ${escapeHtml(agent.agent_proof.evidence_cap)}</p>
        <pre>${escapeHtml(JSON.stringify(agent.metrics.category_metrics, null, 2))}</pre>
      </article>`).join("");
    byId("comparePanel").classList.remove("hidden");
    byId("comparePanel").scrollIntoView({ behavior: "smooth", block: "center" });
  } catch (error) {
    toast(`Comparison failed: ${error.message}`, true);
  }
}

async function loadStatus() {
  const [runtime, network, ledger, gate] = await Promise.allSettled([
    api("/api/runtime"),
    api("/api/network?chain_id=97"),
    api("/api/evidence/verify"),
    api("/api/submission/validate"),
  ]);
  if (runtime.status === "fulfilled") {
    state.runtime = runtime.value;
    const demo = runtime.value.execution_mode === "demo";
    setStatus("runtimeStatus", demo ? "Safe demo mode" : runtime.value.execution_mode, demo ? "warn" : "ok");
  } else setStatus("runtimeStatus", "Unavailable", "bad");
  if (network.status === "fulfilled") {
    const healthy = network.value.chain_id === 97 && Number.isInteger(network.value.block_number);
    setStatus("chainStatus", healthy ? `BSC testnet #${network.value.block_number}` : "RPC mismatch", healthy ? "ok" : "bad");
    byId("chainMeta").textContent = healthy ? "Live JSON-RPC confirmation" : (network.value.error || "Could not verify chain");
    byId("networkDot").className = `dot ${healthy ? "ok" : "bad"}`;
    byId("networkLabel").textContent = healthy ? "BSC testnet online" : "BSC testnet unavailable";
  } else {
    setStatus("chainStatus", "RPC unavailable", "bad");
    byId("networkDot").className = "dot bad";
    byId("networkLabel").textContent = "BSC check failed";
  }
  if (ledger.status === "fulfilled") setStatus("ledgerStatus", ledger.value.valid ? `${ledger.value.records} entries · valid` : "Integrity failed", ledger.value.valid ? "ok" : "bad");
  else setStatus("ledgerStatus", "Unavailable", "bad");
  if (gate.status === "fulfilled") setStatus("gateStatus", gate.value.ready ? "Ready for submission" : `${gate.value.blockers.length} honest blockers`, gate.value.ready ? "ok" : "warn");
  else setStatus("gateStatus", "Unavailable", "bad");
}

async function boot() {
  updateWalletButton();
  const agents = await api("/api/agents");
  state.agents = agents.agents;
  renderCategories();
  renderAgents();
  await loadStatus();
}

byId("categories").addEventListener("click", (event) => {
  const button = event.target.closest("[data-category]");
  if (!button) return;
  state.category = button.dataset.category;
  renderCategories();
  renderAgents();
});

byId("agents").addEventListener("click", (event) => {
  const hire = event.target.closest("[data-hire]");
  if (hire) selectAgent(hire.dataset.hire);
});

byId("agents").addEventListener("change", (event) => {
  const checkbox = event.target.closest("[data-compare]");
  if (!checkbox) return;
  if (checkbox.checked && state.selected.size >= 3) {
    checkbox.checked = false;
    toast("Choose no more than three agents.", true);
    return;
  }
  checkbox.checked ? state.selected.add(checkbox.dataset.compare) : state.selected.delete(checkbox.dataset.compare);
  renderAgents();
});

byId("compareButton").addEventListener("click", compareSelected);
byId("closeCompare").addEventListener("click", () => byId("comparePanel").classList.add("hidden"));
byId("walletButton").addEventListener("click", connectWallet);
byId("previewButton").addEventListener("click", previewAgent);
byId("hireButton").addEventListener("click", hireAgent);
byId("approveButton").addEventListener("click", approveTask);
byId("executeButton").addEventListener("click", executeTask);
byId("revokeButton").addEventListener("click", revokePermission);
byId("resetExample").addEventListener("click", () => {
  if (state.activeCard) byId("taskInput").value = JSON.stringify(state.activeCard.example_input, null, 2);
});

if (globalThis.ethereum?.on) {
  globalThis.ethereum.on("accountsChanged", (accounts) => {
    if (!accounts?.length || accounts[0].toLowerCase() !== state.wallet?.toLowerCase()) {
      clearWalletSession();
      toast("Wallet account changed. Sign in again to control permissions.");
    }
  });
  globalThis.ethereum.on("chainChanged", () => loadStatus());
}

boot().catch((error) => {
  toast(`SafeHire could not start: ${error.message}`, true);
  setStatus("runtimeStatus", "Startup failed", "bad");
});
