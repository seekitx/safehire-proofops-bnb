"use strict";

const LABELS = {
  rebalancing: "Rebalancing",
  grid_trading: "Grid trading",
  yield_optimisation: "Yield optimisation",
  health_factor_monitoring: "Health-factor monitoring",
};

const CRITERIA = [
  ["functionality", "Functionality"],
  ["data_quality", "Data Quality"],
  ["agent_diversity", "Agent Diversity"],
];

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function words(value) {
  return String(value || "").replaceAll("_", " ");
}

async function fetchJson(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error(`${path} returned HTTP ${response.status}`);
  return response.json();
}

function statusChip(status) {
  return node("span", `status ${status}`, words(status));
}

function renderChecks(container, checks) {
  const list = node("div", "check-list");
  for (const [label, passed] of Object.entries(checks || {})) {
    list.append(node("div", `check ${passed === true ? "pass" : ""}`, words(label)));
  }
  container.append(list);
}

function renderCriterion(grid, title, criterion) {
  const card = node("article", "criterion");
  const head = node("div", "criterion-head");
  head.append(node("h3", "", title), statusChip(criterion.status || "blocked"));
  card.append(head, node("p", "", criterion.judge_message || "No judge message was generated."));
  renderChecks(card, criterion.checks);
  grid.append(card);
}

function renderCategory(grid, row) {
  const card = node("article", "category-card");
  const head = node("div", "category-head");
  head.append(
    node("h3", "", LABELS[row.category] || row.category || "Unknown category"),
    statusChip(row.status === "ready" ? "structure_present" : "blocked"),
  );
  card.append(head, node("code", "", String(row.skill_id || "missing skill")));
  const metric = node("div", "metric");
  metric.append(
    node("span", "", `ERC-8004 #${row.erc8004_token_id || "—"}`),
    node("strong", "", `${row.depth_coverage || "0/0"} route checks`),
  );
  card.append(metric);
  card.append(node("p", "fine", "Code and catalog coverage only. Live activation, useful delivery and settlement still need task-level evidence."));
  renderChecks(card, row.dimensions);
  grid.append(card);
}

function renderGate(container, gate) {
  const card = node("article", "gate");
  const head = node("div", "gate-head");
  head.append(node("h3", "", words(gate.id)), statusChip(gate.status || "manual_required"));
  card.append(
    head,
    node("p", "", gate.action || "No action was generated."),
    node("p", "", gate.why_it_matters || ""),
    node("p", "fine", `Acceptance evidence: ${gate.completion_evidence || "Not specified"}`),
  );
  const routes = {
    external_paid_delivery: ["/hire-live", "Open live hire"],
    independent_blind_review: ["/benchmark", "Open human comparison lab"],
    second_operator: ["/", "Inspect current providers"],
    judge_delivery_reliability: ["/health/ready", "Check current storage readiness"],
  };
  const route = routes[gate.id];
  if (route) {
    const link = node("a", "", route[1]);
    link.href = route[0];
    card.append(link);
  }
  container.append(card);
}

function renderPartner(grid, title, partner) {
  const card = node("article", "partner-card");
  const head = node("div", "partner-head");
  head.append(node("h3", "", title), statusChip(partner.status || "not_claimed"));
  card.append(head, node("p", "", partner.boundary || "No evidence boundary was generated."));
  const facts = Object.entries(partner)
    .filter(([key]) => !["status", "boundary"].includes(key));
  for (const [key, value] of facts) {
    card.append(node("p", "fine", `${words(key)}: ${typeof value === "boolean" ? (value ? "present" : "not verified") : String(value ?? "not verified")}`));
  }
  grid.append(card);
}

function renderEvidenceBoundary(scorecard) {
  const evidence = scorecard.evidence_integrity || {};
  const fresh = evidence.catalog_freshness || {};
  const panel = document.querySelector("#evidenceSummary");
  panel.replaceChildren(
    node("p", "", `Catalog: ${fresh.status || "unknown"}. Source observed: ${fresh.source_observed_at || "not recorded"}.`),
    node("p", "", `Paid deliveries replayed in this response: ${evidence.freshly_replayed_paid_deliveries ?? 0}. Candidate files: ${evidence.paid_candidate_files ?? 0}. Declared operator labels: ${evidence.declared_operator_labels ?? 0}.`),
    node("p", "fine", "This response summarizes stored evidence. Page load does not contact every provider or replay every chain receipt. Zero replayed deliveries means none were verified in this response; it does not prove no payment ever happened."),
  );
}

async function loadScorecard() {
  const scorecard = await fetchJson("/api/judge-scorecard");
  renderEvidenceBoundary(scorecard);

  const criteriaGrid = document.querySelector("#criteriaGrid");
  criteriaGrid.replaceChildren();
  for (const [key, title] of CRITERIA) {
    renderCriterion(criteriaGrid, title, scorecard.main_track?.[key] || {});
  }

  const categoryGrid = document.querySelector("#categoryGrid");
  categoryGrid.replaceChildren();
  for (const row of scorecard.category_parity || []) renderCategory(categoryGrid, row);

  const manualGates = document.querySelector("#manualGates");
  manualGates.replaceChildren();
  for (const gate of scorecard.manual_gates || []) renderGate(manualGates, gate);

  const partnerGrid = document.querySelector("#partnerGrid");
  partnerGrid.replaceChildren();
  const partners = scorecard.partner_tracks || {};
  renderPartner(partnerGrid, "TermiX", partners.termix || {});
  renderPartner(partnerGrid, "PancakeSwap", partners.pancakeswap || {});
  renderPartner(partnerGrid, "Altana", partners.altana || {});

  const readinessStatus = scorecard.readiness?.winner_readiness || "conditional";
  const readiness = document.querySelector("#winnerReadiness");
  readiness.textContent = words(readinessStatus).toUpperCase();
  readiness.className = readinessStatus;
  document.querySelector("#winnerBoundary").textContent =
    scorecard.readiness?.headline || scorecard.honesty_boundary || "No readiness boundary was generated.";
  document.querySelector("#observedAt").textContent =
    `Self-audit generated ${new Date(scorecard.generated_at).toLocaleString()}`;
}

document.addEventListener("DOMContentLoaded", () => {
  loadScorecard().catch((error) => {
    const errorNode = document.querySelector("#loadError");
    errorNode.hidden = false;
    errorNode.textContent =
      `The canonical scorecard API failed closed: ${error.message}. No browser-side score was substituted.`;
    document.querySelector("#winnerReadiness").textContent = "LIVE CHECK FAILED";
    document.querySelector("#winnerBoundary").textContent =
      "Open the marketplace, proof dossier and public APIs separately.";
    document.querySelector("#criteriaGrid").replaceChildren();
  });
});
