"use strict";

const REQUIRED_CATEGORIES = [
  "rebalancing",
  "grid_trading",
  "yield_optimisation",
  "health_factor_monitoring",
];

const LABELS = {
  rebalancing: "Rebalancing",
  grid_trading: "Grid trading",
  yield_optimisation: "Yield optimisation",
  health_factor_monitoring: "Health-factor monitoring",
};

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

function checkMap(submission) {
  return new Map(
    (Array.isArray(submission.checks) ? submission.checks : []).map((item) => [
      item.check_id,
      item.passed === true,
    ]),
  );
}

function statusChip(status) {
  return node("span", `status ${status}`, status.replaceAll("_", " "));
}

function renderChecks(container, checks) {
  const list = node("div", "check-list");
  for (const [label, passed] of checks) {
    const item = node("div", `check ${passed ? "pass" : ""}`, label);
    list.append(item);
  }
  container.append(list);
}

function renderCriterion(grid, title, status, message, checks) {
  const card = node("article", "criterion");
  const head = node("div", "criterion-head");
  head.append(node("h3", "", title), statusChip(status));
  card.append(head, node("p", "", message));
  renderChecks(card, checks);
  grid.append(card);
}

function renderCategory(grid, agent) {
  const card = node("article", "category-card");
  const head = node("div", "category-head");
  const category = String(agent.category || "unknown");
  head.append(
    node("h3", "", LABELS[category] || category),
    statusChip(agent.currently_callable ? "ready" : "blocked"),
  );
  card.append(head);
  card.append(
    node("p", "", String(agent.description || "No live description returned.")),
    node("code", "", String(agent.skill_id || "missing skill")),
  );
  const metric = node("div", "metric");
  metric.append(
    node("span", "", `ERC-8004 #${agent.token_id || "—"}`),
    node("strong", "", agent.currently_callable ? "Callable" : "Unavailable"),
  );
  card.append(metric);
  grid.append(card);
}

function renderGate(container, title, complete, action, why) {
  const card = node("article", "gate");
  const head = node("div", "gate-head");
  head.append(node("h3", "", title), statusChip(complete ? "ready" : "manual_required"));
  card.append(head, node("p", "", action), node("p", "", why));
  container.append(card);
}

function renderPartner(grid, title, status, summary) {
  const card = node("article", "partner-card");
  const head = node("div", "partner-head");
  head.append(node("h3", "", title), statusChip(status));
  card.append(head, node("p", "", summary));
  grid.append(card);
}

async function loadScorecard() {
  const [submission, market, proof, termix] = await Promise.all([
    fetchJson("/api/submission/validate"),
    fetchJson("/api/live-market"),
    fetchJson("/api/public-proof"),
    fetchJson("/api/evidence/termix/report"),
  ]);
  const checks = checkMap(submission);
  const agents = Array.isArray(market.agents) ? market.agents : [];
  const categories = new Set(agents.map((item) => item.category));
  const allCategories = REQUIRED_CATEGORIES.every((item) => categories.has(item));
  const callableCount = agents.filter((item) => item.currently_callable === true).length;
  const paidDeliveries = agents.reduce(
    (sum, item) => sum + Number(item.safehire_paid_deliveries || 0),
    0,
  );
  const operatorCount = Number(market.operator_count || 0);
  const indexedSignals = agents.filter(
    (item) => item.market_signals && item.market_signals.available === true,
  ).length;
  const termixTasks = Array.isArray(termix.tasks) ? termix.tasks.length : 0;
  const erc8183 = proof.erc8183 || {};
  const testnetSettled =
    erc8183.status === "completed" ||
    Number(erc8183.provider_paid_u || 0) > 0 ||
    (Array.isArray(erc8183.transactions) &&
      erc8183.transactions.some((item) => item.step === "settle_job"));
  const gateReady = submission.ready === true;

  const functionalityStatus =
    gateReady && callableCount === 4 && testnetSettled
      ? paidDeliveries > 0
        ? "ready"
        : "conditional"
      : "blocked";
  const dataStatus =
    checks.get("live_bsc_market_catalog") && indexedSignals === 4
      ? paidDeliveries > 0 && operatorCount > 1
        ? "ready"
        : "conditional"
      : "blocked";
  const diversityStatus =
    allCategories && agents.length >= 4
      ? operatorCount > 1
        ? "ready"
        : "conditional"
      : "blocked";

  const criteriaGrid = document.querySelector("#criteriaGrid");
  criteriaGrid.replaceChildren();
  renderCriterion(
    criteriaGrid,
    "Functionality",
    functionalityStatus,
    paidDeliveries > 0
      ? "A live external hire has a captured delivery and settlement."
      : "The quote-to-hire route and a complete testnet settlement exist; the first paid external delivery is still a manual proof gate.",
    [
      ["Submission gate has no P0 blocker", gateReady],
      ["Four live skills are callable now", callableCount === 4],
      ["Completed ERC-8183 settlement is inspectable", testnetSettled],
      ["Paid external delivery is captured", paidDeliveries > 0],
    ],
  );
  renderCriterion(
    criteriaGrid,
    "Data Quality",
    dataStatus,
    "Registration, endpoint health, source and freshness stay separate. Outcome history is not inferred from identity or index scores.",
    [
      ["Live BSC catalog passes", checks.get("live_bsc_market_catalog") === true],
      ["Official-index signals returned for four agents", indexedSignals === 4],
      ["Three or more raw TermiX task pairs exist", termixTasks >= 3],
      ["Paid outcome history exists", paidDeliveries > 0],
      ["More than one independent operator", operatorCount > 1],
    ],
  );
  renderCriterion(
    criteriaGrid,
    "Agent Diversity",
    diversityStatus,
    "Every required category has an ERC-8004 identity, category-specific input, quote and hire route. Current supplier diversity remains one operator.",
    [
      ["Rebalancing is present", categories.has("rebalancing")],
      ["Grid trading is present", categories.has("grid_trading")],
      ["Yield optimisation is present", categories.has("yield_optimisation")],
      ["Health-factor monitoring is present", categories.has("health_factor_monitoring")],
      ["Second operator is present", operatorCount > 1],
    ],
  );

  const categoryGrid = document.querySelector("#categoryGrid");
  categoryGrid.replaceChildren();
  for (const category of REQUIRED_CATEGORIES) {
    const agent = agents.find((item) => item.category === category) || { category };
    renderCategory(categoryGrid, agent);
  }

  const manualGates = document.querySelector("#manualGates");
  manualGates.replaceChildren();
  renderGate(
    manualGates,
    "First external paid delivery",
    paidDeliveries > 0,
    "Complete one bounded 0.10 U ERC-8183 hire from a live card and preserve create, fund, deliver and settle receipts.",
    "This is the difference between an implemented path and an independently auditable marketplace track record.",
  );
  renderGate(
    manualGates,
    "Independent blind quality review",
    false,
    "Use the benchmark lab for at least three human no-Agent runs and have another person score hidden A/B outputs.",
    "Automated scoring is useful regression evidence, but it is not independent research.",
  );
  renderGate(
    manualGates,
    "Second ERC-8004 operator",
    operatorCount > 1,
    "Validate and onboard a second provider with callable endpoint, identity and category fit.",
    "Four skills from one seller prove breadth, not marketplace choice.",
  );
  renderGate(
    manualGates,
    "Judge-period delivery reliability",
    false,
    "Keep the public service warm during judging and publish a 2–3 minute single-path demo.",
    "A cold start or scattered navigation can hide working code from a time-constrained judge.",
  );

  const partnerGrid = document.querySelector("#partnerGrid");
  partnerGrid.replaceChildren();
  renderPartner(
    partnerGrid,
    "TermiX",
    termixTasks >= 3 ? "conditional" : "blocked",
    `${termixTasks} raw task pairs are published. Independent human timing and blind review remain outstanding.`,
  );
  renderPartner(
    partnerGrid,
    "PancakeSwap",
    checks.get("pancakeswap_live_benefit") ? "conditional" : "blocked",
    "Same-block route and gas-aware benefit evidence exists. It is explicitly not presented as realised profit.",
  );
  renderPartner(
    partnerGrid,
    "Altana",
    "not_claimed",
    "No eligibility claim is made without a real scoped session-key transaction and in-product revocation receipt.",
  );

  const readiness = document.querySelector("#winnerReadiness");
  readiness.textContent =
    paidDeliveries > 0 && operatorCount > 1 ? "READY, SUBJECT TO LIVE REVIEW" : "CONDITIONAL";
  readiness.className = functionalityStatus;
  document.querySelector("#winnerBoundary").textContent =
    "Working MVP and protocol evidence are strong. Adoption and independent-quality claims stay conditional until their manual evidence exists.";
  document.querySelector("#observedAt").textContent =
    `Public state checked ${new Date().toISOString()}`;
}

document.addEventListener("DOMContentLoaded", () => {
  loadScorecard().catch((error) => {
    const errorNode = document.querySelector("#loadError");
    errorNode.hidden = false;
    errorNode.textContent =
      `Live self-audit could not be completed: ${error.message}. ` +
      "No stale values were substituted.";
    document.querySelector("#winnerReadiness").textContent = "LIVE CHECK FAILED";
    document.querySelector("#winnerBoundary").textContent =
      "Open the marketplace, proof dossier and public APIs separately. This page fails closed.";
    document.querySelector("#criteriaGrid").replaceChildren();
  });
});
