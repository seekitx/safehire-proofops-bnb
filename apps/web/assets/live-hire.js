"use strict";

const CHAIN_ID_HEX = "0x38";
const EXPLORER = "https://bscscan.com";
const PRICE_RAW = 100000000000000000n;
const U_TOKEN = "0xcE24439F2D9C6a2289F741120FE202248B666666";
const COMMERCE = "0xEa4DAa3100A767e86FDed867729ae7446476EBA6";
const SKILLS = new Set(["rebalance_plan", "grid_plan", "yield_plan", "health_factor"]);
const WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c";
const USDT = "0x55d398326f99059fF775485246999027B3197955";
const STORAGE_KEY = "safehire-live-hire-v2";

const examples = {
  rebalance_plan: {
    holdings: [{ token: WBNB, usd: 600 }, { token: USDT, usd: 400 }],
    targets: { [WBNB]: 50, [USDT]: 50 },
  },
  grid_plan: { token: WBNB, capitalUsd: 1000, levels: 9, bandPct: 5 },
  yield_plan: { amountUsd: 10000, from: "Venus Core USDT", currentApyPct: 2.5 },
  health_factor: { address: "0x0000000000000000000000000000000000000000" },
};

const state = {
  skillId: null,
  agentTokenId: null,
  quotePayload: null,
  owner: null,
  plan: null,
  transactions: [],
  results: [],
  jobId: null,
  active: false,
  notifyResult: null,
  settleTransaction: null,
  disputeTransaction: null,
  refundTransaction: null,
  delivery: null,
  receipt: null,
  fundingReady: false,
  writeEnabled: false,
};

const byId = (id) => document.getElementById(id);
let toastTimer;

function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 6500);
}

function short(value, head = 9, tail = 7) {
  const text = String(value || "");
  return text.length > head + tail + 2 ? `${text.slice(0, head)}…${text.slice(-tail)}` : text;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'\"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '\"': "&quot;",
  })[character]);
}

function unixTime(value) {
  const parsed = Number(value || 0);
  return parsed > 0 ? new Date(parsed * 1000).toLocaleString() : "—";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Accept: "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
  return body;
}

function selectedInput() {
  let value;
  try {
    value = JSON.parse(byId("taskInput").value);
  } catch (error) {
    throw new Error(`Task JSON is invalid: ${error.message}`);
  }
  if (!value || Array.isArray(value) || typeof value !== "object") {
    throw new Error("Task input must be a JSON object");
  }
  return value;
}

function taskExample() {
  const value = structuredClone(examples[state.skillId]);
  if (state.skillId === "health_factor" && state.owner) value.address = state.owner;
  return value;
}

function resetTask() {
  byId("taskInput").value = JSON.stringify(taskExample(), null, 2);
}

function setStep(step, status, detail) {
  const row = document.querySelector(`[data-step="${step}"]`);
  if (!row) return;
  row.classList.toggle("active", status === "active");
  row.classList.toggle("done", status === "done");
  row.querySelector("small").innerHTML = detail;
}

function resetSteps() {
  document.querySelectorAll("[data-step]").forEach((row) => {
    row.classList.remove("active", "done");
    row.querySelector("small").textContent = "Waiting";
  });
}

function currentTransaction() {
  const completed = new Set(state.results.map((item) => item.step));
  return state.transactions.find((transaction) => !completed.has(transaction.step)) || null;
}

function walletTransaction(transaction) {
  return {
    from: state.owner,
    to: transaction.to,
    data: transaction.data,
    value: transaction.value || "0x0",
  };
}

function extractJobId(receipt) {
  const topic = String(state.plan.job_created_topic).toLowerCase();
  const commerce = String(state.plan.commerce_address).toLowerCase();
  const log = (receipt.logs || []).find(
    (item) => item.address?.toLowerCase() === commerce && item.topics?.[0]?.toLowerCase() === topic,
  );
  if (!log?.topics?.[1]) throw new Error("The JobCreated event was not found in the receipt");
  return Number(BigInt(log.topics[1]));
}

function persistJob() {
  if (!state.jobId) return;
  const record = {
    job_id: state.jobId,
    skill_id: state.skillId,
    agent_token_id: state.agentTokenId,
    owner: state.owner,
    saved_at: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, JSON.stringify(record));
  const url = new URL(location.href);
  url.searchParams.set("job_id", String(state.jobId));
  url.searchParams.set("skill_id", state.skillId);
  if (state.agentTokenId) url.searchParams.set("agent_token_id", String(state.agentTokenId));
  history.replaceState(null, "", url);
}

function savedJob() {
  const params = new URLSearchParams(location.search);
  const queryJob = Number(params.get("job_id") || 0);
  if (Number.isSafeInteger(queryJob) && queryJob > 0) return queryJob;
  try {
    const record = JSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
    return Number.isSafeInteger(record?.job_id) && record.job_id > 0 ? record.job_id : null;
  } catch (_error) {
    return null;
  }
}

async function waitForReceipt(txHash) {
  const deadline = Date.now() + 6 * 60 * 1000;
  while (Date.now() < deadline) {
    const receipt = await ethereum.request({ method: "eth_getTransactionReceipt", params: [txHash] });
    if (receipt) return receipt;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error("Receipt was not confirmed within six minutes; check BscScan before retrying");
}

async function ensureMainnet() {
  const current = await ethereum.request({ method: "eth_chainId" });
  if (current === CHAIN_ID_HEX) return;
  try {
    await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
  } catch (error) {
    if (error.code !== 4902) throw error;
    await ethereum.request({
      method: "wallet_addEthereumChain",
      params: [{
        chainId: CHAIN_ID_HEX,
        chainName: "BNB Smart Chain Mainnet",
        nativeCurrency: { name: "BNB", symbol: "BNB", decimals: 18 },
        rpcUrls: ["https://bsc-dataseed.bnbchain.org"],
        blockExplorerUrls: [EXPLORER],
      }],
    });
  }
}

function encodeAddressWord(address) {
  return String(address).toLowerCase().replace(/^0x/, "").padStart(64, "0");
}

async function readBalances() {
  const [bnbHex, uHex] = await Promise.all([
    ethereum.request({ method: "eth_getBalance", params: [state.owner, "latest"] }),
    ethereum.request({
      method: "eth_call",
      params: [{ to: U_TOKEN, data: `0x70a08231${encodeAddressWord(state.owner)}` }, "latest"],
    }),
  ]);
  const bnb = BigInt(bnbHex);
  const u = BigInt(uHex);
  byId("bnbBalance").textContent = `${(Number(bnb) / 1e18).toFixed(6)} BNB`;
  byId("uBalance").textContent = `${(Number(u) / 1e18).toFixed(4)} U`;
  const gasReady = bnb > 0n;
  const uReady = u >= PRICE_RAW;
  byId("bnbBalance").parentElement.classList.toggle("ready", gasReady);
  byId("uBalance").parentElement.classList.toggle("ready", uReady);
  byId("gasReadiness").textContent = gasReady ? "Gas available" : "Needs BNB gas";
  byId("uReadiness").textContent = uReady ? "0.10 U available" : "Insufficient for hire";
  return { gasReady, uReady };
}

function showQuote(payload) {
  const quote = payload.quote || {};
  const verification = payload.quote_verification || {};
  state.quotePayload = payload;
  state.agentTokenId = Number(payload.agent?.erc8004_token_id || state.agentTokenId || 0) || null;
  byId("agentName").textContent = payload.agent?.name || state.skillId;
  byId("agentDeliverable").textContent = quote.deliverables || "No deliverable description returned.";
  byId("quotePrice").textContent = quote.price_display || "0.10 U";
  byId("quoteProvider").textContent = short(quote.provider);
  byId("quoteProvider").title = quote.provider || "";
  byId("quoteEta").textContent = `${quote.estimated_completion_seconds || "—"} sec`;
  byId("identityLink").textContent = `ERC-8004 #${payload.agent?.erc8004_token_id || "—"} ↗`;
  byId("identityLink").href = payload.agent?.registration_url || "#";
  byId("quoteSignature").textContent = verification.signature_method
    ? `${verification.signature_method.toUpperCase()} · ${short(verification.negotiation_hash)}`
    : "Verified during final prepare";
  byId("quoteExpiry").textContent = unixTime(quote.quote_expires_at);
  byId("quoteState").textContent = verification.signature_method ? "SIGNED · 0 TX" : "PREVIEW · 0 TX";
  byId("taskNeeds").innerHTML = (quote.success_criteria || [])
    .map((item) => `<li>${escapeHtml(item)}</li>`)
    .join("");
}

async function loadRuntime() {
  const runtime = await api("/api/runtime");
  state.writeEnabled = runtime.external_mainnet_hire_enabled === true;
  if (!state.writeEnabled) {
    byId("prepareHire").disabled = true;
    byId("prepareNote").textContent =
      "This deployment exposes read-only proof only; external mainnet hire plans are disabled by configuration.";
  }
}

async function loadQuote() {
  const params = new URLSearchParams(location.search);
  const requested = params.get("skill_id") || "grid_plan";
  state.skillId = SKILLS.has(requested) ? requested : "grid_plan";
  const token = Number(params.get("agent_token_id") || 0);
  state.agentTokenId = Number.isSafeInteger(token) && token > 0 ? token : null;
  resetTask();
  try {
    const payload = await api("/api/live-market/quote", {
      method: "POST",
      body: JSON.stringify({ skill_id: state.skillId, agent_token_id: state.agentTokenId }),
    });
    showQuote(payload);
  } catch (error) {
    byId("quoteState").textContent = "UNAVAILABLE";
    toast(`Signed quote unavailable: ${error.message}`, true);
  }
}

async function connectWallet() {
  if (!window.ethereum) return toast("No EVM wallet was found in this browser.", true);
  try {
    const accounts = await ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts?.[0]) throw new Error("Wallet returned no account");
    await ensureMainnet();
    state.owner = accounts[0];
    byId("buyerAddress").textContent = state.owner;
    byId("connectWallet").textContent = short(state.owner);
    byId("networkLabel").textContent = "BSC Mainnet · wallet connected";
    byId("networkDot").className = "dot ok";
    if (state.skillId === "health_factor") resetTask();
    const readiness = await readBalances();
    state.fundingReady = readiness.gasReady && readiness.uReady;
    byId("prepareHire").disabled = !state.writeEnabled;
    byId("prepareHire").textContent = "Prepare fresh signed 0.10 U hire";
    byId("prepareNote").textContent = state.writeEnabled
      ? state.fundingReady
        ? "Balances are sufficient. Preparing remains read-only and verifies a fresh provider signature."
        : "You can inspect the signed plan, but sending stays locked until this wallet has BNB gas and at least 0.10 U."
      : "This deployment has external mainnet writes disabled.";
    const jobId = savedJob();
    if (jobId) await resumeJob(jobId);
  } catch (error) {
    toast(`Wallet connection stopped: ${error.message}`, true);
  }
}

function updateReceipt(title = "Job activity") {
  state.receipt = {
    schema_version: "2.0",
    verification_status: "browser_activity_draft",
    evidence_mode: "live",
    chain_id: 56,
    skill_id: state.skillId,
    erc8004_token_id: state.agentTokenId,
    agent: state.plan?.agent || state.quotePayload?.agent,
    quote: state.plan?.quote || state.quotePayload?.quote,
    quote_verification: state.plan?.quote_verification,
    buyer: state.owner,
    job_id: state.jobId,
    task_input: state.plan?.task_input,
    transactions: state.results,
    agent_notification: state.notifyResult,
    delivery: state.delivery,
    observed_at: new Date().toISOString(),
    boundary:
      "This browser activity draft is not the server-verified paid-delivery dossier. Use the verified download after completion.",
  };
  byId("receiptPanel").hidden = false;
  byId("receiptTitle").textContent = title;
  byId("receiptJson").textContent = JSON.stringify(state.receipt, null, 2);
}

async function prepareHire() {
  if (!state.owner || !state.quotePayload || !state.writeEnabled) return;
  if (!byId("riskConfirm").checked) {
    return toast("Confirm the BSC Mainnet risk statement first.", true);
  }
  try {
    const taskInput = selectedInput();
    state.plan = await api("/api/live-hire/prepare", {
      method: "POST",
      body: JSON.stringify({
        buyer: state.owner,
        skill_id: state.skillId,
        agent_token_id: state.agentTokenId,
        task_input: taskInput,
      }),
    });
    showQuote(state.plan);
    state.transactions = [state.plan.transaction];
    state.results = [];
    state.jobId = null;
    resetSteps();
    setStep("create_job", "active", "Fresh provider signature verified; ready for wallet confirmation");
    byId("nextAction").textContent = state.plan.transaction.label;
    byId("sendNext").textContent = state.plan.transaction.label;
    byId("sendNext").disabled = !state.fundingReady;
    byId("jobBadge").textContent = "SIGNED PLAN VERIFIED";
    byId("prepareHire").textContent = "Signed plan prepared · prepare again after edits";
    byId("quoteExpiry").textContent = unixTime(state.plan.timeline?.quote_expires_at);
    updateReceipt("Fresh signed transaction plan prepared");
    toast(state.fundingReady
      ? "Signed plan verified. No transaction has been sent."
      : "Signed plan ready for inspection. Sending is locked because the wallet balance is insufficient.");
  } catch (error) {
    toast(`Plan stopped: ${error.message}`, true);
  }
}

async function preflightTransaction(transaction) {
  if (transaction.valid_until && Math.floor(Date.now() / 1000) >= Number(transaction.valid_until)) {
    throw new Error("The signed quote expired. Prepare a fresh signed plan before creating the job.");
  }
  await ensureMainnet();
  await ethereum.request({ method: "eth_estimateGas", params: [walletTransaction(transaction)] });
}

async function sendNext() {
  const transaction = currentTransaction();
  if (!transaction || !state.owner || state.active) return;
  state.active = true;
  const button = byId("sendNext");
  button.disabled = true;
  button.textContent = `Preflighting ${transaction.label}…`;
  setStep(transaction.step, "active", "Simulating against current BSC state");
  try {
    await preflightTransaction(transaction);
    button.textContent = `Confirm ${transaction.label} in wallet…`;
    setStep(transaction.step, "active", "Waiting for your wallet confirmation");
    const txHash = await ethereum.request({ method: "eth_sendTransaction", params: [walletTransaction(transaction)] });
    setStep(
      transaction.step,
      "active",
      `Submitted · <a href="${EXPLORER}/tx/${txHash}" target="_blank" rel="noreferrer">BscScan ↗</a>`,
    );
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error(`${transaction.label} reverted`);
    state.results.push({
      step: transaction.step,
      tx_hash: txHash,
      block_number: Number.parseInt(receipt.blockNumber, 16),
    });
    setStep(transaction.step, "done", `Confirmed · ${short(txHash)}`);
    if (transaction.step === "create_job") {
      state.jobId = extractJobId(receipt);
      persistJob();
      byId("jobBadge").textContent = `JOB #${state.jobId}`;
      const followup = await api("/api/live-hire/followup-plan", {
        method: "POST",
        body: JSON.stringify({ buyer: state.owner, job_id: state.jobId }),
      });
      state.transactions.push(...followup.transactions);
    }
    const upcoming = currentTransaction();
    if (upcoming) {
      setStep(upcoming.step, "active", "Ready for separate confirmation");
      byId("nextAction").textContent = upcoming.label;
      button.textContent = upcoming.label;
      button.disabled = false;
    } else {
      byId("nextAction").textContent = "Notify the selected provider after escrow funding";
      button.textContent = "Escrow funding complete";
      byId("notifyAgent").disabled = false;
      byId("checkDelivery").disabled = false;
      setStep("agent_delivery", "active", "Funded; provider notification required");
    }
    updateReceipt(`Job #${state.jobId || "—"} transaction confirmed`);
  } catch (error) {
    button.disabled = false;
    button.textContent = `Retry ${transaction.label}`;
    toast(`Wallet action stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

function markFundedPathDone() {
  for (const step of ["create_job", "register_job", "set_budget", "approve_u", "fund_job"]) {
    setStep(step, "done", "Confirmed on-chain");
  }
}

async function resumeJob(jobId) {
  try {
    const status = await api(`/api/live-hire/status/${jobId}`);
    if (state.owner && status.client?.toLowerCase() !== state.owner.toLowerCase()) {
      throw new Error("The connected wallet does not own the saved job");
    }
    state.jobId = jobId;
    state.skillId = status.task_spec.service;
    state.agentTokenId = Number(status.task_spec.erc8004_token_id);
    byId("taskInput").value = JSON.stringify(status.task_spec.task_input, null, 2);
    byId("jobBadge").textContent = `JOB #${jobId} · ${status.status}`;
    byId("resumeState").hidden = false;
    byId("resumeState").textContent =
      `Recovered job #${jobId} from BSC. Browser memory is not trusted; the next action was rebuilt from chain state.`;
    resetSteps();
    setStep("create_job", "done", "Recovered from on-chain job");
    persistJob();

    if (status.status === "OPEN") {
      if (status.open_progress?.policy_registered) setStep("register_job", "done", "Confirmed on-chain");
      if (BigInt(status.budget_raw || 0) === PRICE_RAW) setStep("set_budget", "done", "Confirmed on-chain");
      if (status.open_progress?.exact_allowance) setStep("approve_u", "done", "Exact allowance confirmed");
      const followup = await api("/api/live-hire/followup-plan", {
        method: "POST",
        body: JSON.stringify({ buyer: state.owner, job_id: jobId }),
      });
      state.transactions = followup.transactions;
      state.results = [];
      const next = currentTransaction();
      setStep(next.step, "active", "Recovered next missing action");
      byId("sendNext").textContent = next.label;
      byId("sendNext").disabled = !state.fundingReady;
      byId("nextAction").textContent = next.label;
    } else if (status.can_refund) {
      markFundedPathDone();
      const refund = await api(`/api/live-hire/refund-plan/${jobId}`);
      state.refundTransaction = refund.transaction;
      byId("refundJob").disabled = false;
      byId("nextAction").textContent = refund.transaction.label;
    } else if (status.status === "FUNDED") {
      markFundedPathDone();
      setStep("agent_delivery", "active", "Funded; notify or check provider delivery");
      byId("notifyAgent").disabled = false;
      byId("checkDelivery").disabled = false;
      byId("nextAction").textContent = "Notify provider or check delivery";
    } else if (status.status === "SUBMITTED") {
      markFundedPathDone();
      byId("checkDelivery").disabled = false;
      await inspectDelivery();
    } else if (status.status === "COMPLETED") {
      markFundedPathDone();
      setStep("agent_delivery", "done", "Hash-committed delivery recorded");
      setStep("settle_job", "done", "Completed on-chain");
      byId("downloadReceipt").disabled = false;
      byId("nextAction").textContent = "Download the server-verified paid-delivery dossier";
      try {
        await inspectDelivery();
      } catch (_error) {
        // The completed job itself remains recoverable even if storage is temporarily unavailable.
      }
    }
    updateReceipt(`Job #${jobId} recovered from BSC`);
  } catch (error) {
    toast(`Job recovery stopped: ${error.message}`, true);
  }
}

async function notifyAgent() {
  if (!state.jobId) return;
  const button = byId("notifyAgent");
  button.disabled = true;
  button.textContent = "Notifying funded provider…";
  try {
    state.notifyResult = await api("/api/live-hire/notify", {
      method: "POST",
      body: JSON.stringify({ job_id: state.jobId }),
    });
    setStep("agent_delivery", "active", "Provider acknowledged the funded job");
    button.textContent = state.notifyResult.status === "accepted" ? "Provider notified" : state.notifyResult.status;
    byId("nextAction").textContent = "Poll the chain for the provider's signed submission";
    updateReceipt(`Provider notification for job #${state.jobId}`);
    toast("The provider notification was idempotent and sent no wallet transaction.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry provider notification";
    toast(`Provider notification stopped: ${error.message}`, true);
  }
}

function renderDelivery(delivery) {
  state.delivery = delivery;
  const verification = delivery.verification || {};
  byId("deliveryPanel").hidden = false;
  byId("deliveryTitle").textContent = `Job #${delivery.job_id} · manifest matches ${short(delivery.onchain?.deliverable_hash)}`;
  byId("deliveryManifestLink").href = delivery.manifest_url;
  byId("deliveryContent").textContent = verification.content || "No content returned.";
  const facts = [
    ["HASH", verification.hash_matches],
    ["JOB + CHAIN", verification.job_matches && verification.chain_matches],
    ["CONTRACTS", verification.contracts_match],
    ["HUMAN REVIEW", !verification.human_success_criteria_review_required],
  ];
  byId("deliveryVerification").innerHTML = facts
    .map(([label, passed]) => `<div><small>${label}</small><strong>${passed ? "VERIFIED" : label === "HUMAN REVIEW" ? "REQUIRED" : "FAILED"}</strong></div>`)
    .join("");
  byId("deliveryConfirm").checked = false;
  setStep("agent_delivery", "done", "Manifest content hash matches on-chain commitment");
}

async function inspectDelivery() {
  if (!state.jobId) return;
  const delivery = await api(`/api/live-hire/delivery/${state.jobId}`);
  renderDelivery(delivery);
  const settlement = delivery.settlement || {};
  if (settlement.can_dispute) {
    byId("disputeJob").disabled = false;
  }
  if (settlement.can_settle) {
    const settle = await api(`/api/live-hire/settle-plan/${state.jobId}`);
    state.settleTransaction = settle.transaction;
    setStep("settle_job", "active", `Policy verdict ${settlement.policy_verdict}; human review required`);
    byId("nextAction").textContent = "Review the content, then settle or dispute";
  } else {
    const minutes = Math.max(1, Math.ceil(Number(settlement.seconds_until_settle || 0) / 60));
    setStep("settle_job", "active", settlement.can_dispute
      ? `Review window · about ${minutes} min remaining · dispute available`
      : `Policy review in progress · about ${minutes} min remaining`);
  }
  updateReceipt(`Job #${state.jobId} delivery hash verified`);
  return delivery;
}

async function checkDelivery() {
  if (!state.jobId) return;
  try {
    const status = await api(`/api/live-hire/status/${state.jobId}`);
    if (status.completed) {
      markFundedPathDone();
      setStep("settle_job", "done", "Completed on-chain");
      byId("nextAction").textContent = "Download the server-verified paid-delivery dossier";
      await inspectDelivery();
      return toast(`Job #${state.jobId} is completed on-chain.`);
    }
    if (status.can_refund) {
      const refund = await api(`/api/live-hire/refund-plan/${state.jobId}`);
      state.refundTransaction = refund.transaction;
      byId("refundJob").disabled = false;
      byId("nextAction").textContent = refund.transaction.label;
      return toast("The funded job expired and can be refunded.", true);
    }
    if (status.status === "SUBMITTED") {
      await inspectDelivery();
      return toast("The full manifest was retrieved and its hash matches the on-chain commitment.");
    }
    toast(`Current on-chain status: ${status.status}.`);
  } catch (error) {
    toast(`Delivery check stopped: ${error.message}`, true);
  }
}

async function prepareDispute() {
  if (!state.jobId || !state.owner) return;
  try {
    const plan = await api("/api/live-hire/dispute-plan", {
      method: "POST",
      body: JSON.stringify({ buyer: state.owner, job_id: state.jobId }),
    });
    state.disputeTransaction = plan.transaction;
    await sendFinal(plan.transaction, "dispute");
  } catch (error) {
    toast(`Dispute stopped: ${error.message}`, true);
  }
}

async function sendFinal(transaction, kind) {
  if (!transaction || state.active) return;
  if (kind === "settle" && !byId("deliveryConfirm").checked) {
    return toast("Read the hash-verified delivery and confirm the success-criteria review first.", true);
  }
  state.active = true;
  const button = kind === "settle"
    ? byId("settleJob")
    : kind === "dispute"
      ? byId("disputeJob")
      : byId("refundJob");
  button.disabled = true;
  try {
    await preflightTransaction(transaction);
    const txHash = await ethereum.request({ method: "eth_sendTransaction", params: [walletTransaction(transaction)] });
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error(`${transaction.label} reverted`);
    state.results.push({
      step: transaction.step,
      tx_hash: txHash,
      block_number: Number.parseInt(receipt.blockNumber, 16),
    });
    if (kind === "dispute") {
      setStep("settle_job", "active", "Dispute opened; waiting for policy verdict");
      byId("nextAction").textContent = "Monitor the policy vote and final verdict";
      button.textContent = "Dispute opened";
    } else {
      setStep("settle_job", "done", kind === "settle" ? "Provider payment completed" : "Escrow refunded");
      byId("nextAction").textContent = kind === "settle"
        ? "Download the server-verified paid-delivery dossier"
        : "Refund completed";
      button.textContent = kind === "settle" ? "Settlement complete" : "Refund complete";
    }
    updateReceipt(`Job #${state.jobId} ${kind} transaction confirmed`);
    toast(`Job #${state.jobId} ${kind} transaction confirmed on-chain.`);
  } catch (error) {
    button.disabled = false;
    toast(`${kind} stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

function downloadJson(payload, filename) {
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function downloadReceipt() {
  if (!state.jobId) {
    if (state.receipt) downloadJson(state.receipt, "safehire-browser-plan-draft.json");
    return;
  }
  try {
    const verified = await api(`/api/live-hire/verified-receipt/${state.jobId}`);
    downloadJson(verified, `safehire-mainnet-job-${state.jobId}-verified.json`);
    byId("receiptTitle").textContent = "Server-verified mainnet dossier downloaded";
    toast("Verified dossier downloaded. Commit it under evidence/marketplace/paid-deliveries/. ");
  } catch (error) {
    if (state.receipt) downloadJson(state.receipt, `safehire-job-${state.jobId}-browser-draft.json`);
    toast(`Verified dossier is not ready: ${error.message}. A browser draft was downloaded instead.`, true);
  }
}

byId("resetTask").addEventListener("click", resetTask);
byId("connectWallet").addEventListener("click", connectWallet);
byId("prepareHire").addEventListener("click", prepareHire);
byId("sendNext").addEventListener("click", sendNext);
byId("notifyAgent").addEventListener("click", notifyAgent);
byId("checkDelivery").addEventListener("click", checkDelivery);
byId("settleJob").addEventListener("click", () => sendFinal(state.settleTransaction, "settle"));
byId("disputeJob").addEventListener("click", prepareDispute);
byId("refundJob").addEventListener("click", () => sendFinal(state.refundTransaction, "refund"));
byId("downloadReceipt").addEventListener("click", downloadReceipt);
byId("deliveryConfirm").addEventListener("change", () => {
  byId("settleJob").disabled = !byId("deliveryConfirm").checked || !state.settleTransaction;
});
byId("riskConfirm").addEventListener("change", () => {
  if (state.plan) {
    byId("sendNext").disabled = !byId("riskConfirm").checked
      || !state.fundingReady
      || !currentTransaction();
  }
});

if (window.ethereum?.on) {
  ethereum.on("accountsChanged", () => location.reload());
  ethereum.on("chainChanged", () => location.reload());
}

Promise.all([loadRuntime(), loadQuote()]).catch((error) => {
  toast(`Live hire initialization failed: ${error.message}`, true);
});
