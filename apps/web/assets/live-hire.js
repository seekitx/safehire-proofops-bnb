const CHAIN_ID_HEX = "0x38";
const EXPLORER = "https://bscscan.com";
const PRICE_RAW = 100000000000000000n;
const U_TOKEN = "0xcE24439F2D9C6a2289F741120FE202248B666666";
const COMMERCE = "0xEa4DAa3100A767e86FDed867729ae7446476EBA6";
const SKILLS = new Set(["rebalance_plan", "grid_plan", "yield_plan", "health_factor"]);
const WBNB = "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c";
const USDT = "0x55d398326f99059fF775485246999027B3197955";

const examples = {
  rebalance_plan: { holdings: [{ token: WBNB, usd: 600 }, { token: USDT, usd: 400 }], targets: { [WBNB]: 50, [USDT]: 50 } },
  grid_plan: { token: WBNB, capitalUsd: 1000, levels: 9, bandPct: 5 },
  yield_plan: { amountUsd: 10000, from: "Venus Core USDT", currentApyPct: 2.5 },
  health_factor: { address: "0x0000000000000000000000000000000000000000" },
};

const state = {
  skillId: null,
  quotePayload: null,
  owner: null,
  plan: null,
  transactions: [],
  results: [],
  jobId: null,
  active: false,
  notifyResult: null,
  settleTransaction: null,
  refundTransaction: null,
  receipt: null,
  fundingReady: false,
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
  if (!value || Array.isArray(value) || typeof value !== "object") throw new Error("Task input must be a JSON object");
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

function currentTransaction() {
  const completed = new Set(state.results.map((item) => item.step));
  return state.transactions.find((transaction) => !completed.has(transaction.step)) || null;
}

function walletTransaction(transaction) {
  return { from: state.owner, to: transaction.to, data: transaction.data, value: transaction.value || "0x0" };
}

function extractJobId(receipt) {
  const topic = String(state.plan.job_created_topic).toLowerCase();
  const commerce = String(state.plan.commerce_address).toLowerCase();
  const log = (receipt.logs || []).find((item) => item.address?.toLowerCase() === commerce && item.topics?.[0]?.toLowerCase() === topic);
  if (!log?.topics?.[1]) throw new Error("The JobCreated event was not found in the receipt");
  return Number(BigInt(log.topics[1]));
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
    ethereum.request({ method: "eth_call", params: [{ to: U_TOKEN, data: `0x70a08231${encodeAddressWord(state.owner)}` }, "latest"] }),
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

async function loadQuote() {
  const params = new URLSearchParams(location.search);
  const requested = params.get("skill_id") || "grid_plan";
  state.skillId = SKILLS.has(requested) ? requested : "grid_plan";
  resetTask();
  try {
    const payload = await api("/api/live-market/quote", { method: "POST", body: JSON.stringify({ skill_id: state.skillId }) });
    state.quotePayload = payload;
    const quote = payload.quote || {};
    byId("agentName").textContent = payload.agent?.name || state.skillId;
    byId("agentDeliverable").textContent = quote.deliverables || "No deliverable description returned.";
    byId("quotePrice").textContent = quote.price_display || "0.10 U";
    byId("quoteProvider").textContent = short(quote.provider);
    byId("quoteProvider").title = quote.provider || "";
    byId("quoteEta").textContent = `${quote.estimated_completion_seconds || "—"} sec`;
    byId("identityLink").textContent = `ERC-8004 #${payload.agent?.erc8004_token_id || "—"} ↗`;
    byId("identityLink").href = payload.agent?.registration_url || "#";
    byId("quoteState").textContent = "LIVE · 0 TX";
    byId("taskNeeds").innerHTML = Object.entries(quote.needs || {}).map(([key, value]) => `<li><code>${escapeHtml(key)}</code><br/>${escapeHtml(value)}</li>`).join("");
  } catch (error) {
    byId("quoteState").textContent = "UNAVAILABLE";
    toast(`Live quote unavailable: ${error.message}`, true);
  }
}

async function connectWallet() {
  if (!window.ethereum) return toast("No EVM wallet was found in Chrome.", true);
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
    byId("prepareHire").disabled = false;
    byId("prepareHire").textContent = "Prepare exact 0.10 U hire plan";
    byId("prepareNote").textContent = state.fundingReady
      ? "Balances are sufficient. Preparing remains read-only."
      : "You can inspect the plan, but sending stays locked until this wallet has BNB gas and at least 0.10 U.";
  } catch (error) {
    toast(`Wallet connection stopped: ${error.message}`, true);
  }
}

function updateReceipt(title = "Job activity") {
  state.receipt = {
    schema_version: "1.0",
    evidence_mode: "live",
    chain_id: 56,
    skill_id: state.skillId,
    agent: state.plan?.agent || state.quotePayload?.agent,
    quote: state.plan?.quote || state.quotePayload?.quote,
    buyer: state.owner,
    job_id: state.jobId,
    task_input: state.plan?.task_input,
    transactions: state.results,
    agent_notification: state.notifyResult,
    observed_at: new Date().toISOString(),
  };
  byId("receiptPanel").hidden = false;
  byId("receiptTitle").textContent = title;
  byId("receiptJson").textContent = JSON.stringify(state.receipt, null, 2);
}

async function prepareHire() {
  if (!state.owner || !state.quotePayload) return;
  if (!byId("riskConfirm").checked) return toast("Confirm the BSC Mainnet risk statement first.", true);
  try {
    const taskInput = selectedInput();
    state.plan = await api("/api/live-hire/prepare", {
      method: "POST",
      body: JSON.stringify({ buyer: state.owner, skill_id: state.skillId, task_input: taskInput }),
    });
    state.transactions = [state.plan.transaction];
    state.results = [];
    state.jobId = null;
    setStep("create_job", "active", "Ready for wallet confirmation");
    byId("nextAction").textContent = state.plan.transaction.label;
    byId("sendNext").textContent = state.plan.transaction.label;
    byId("sendNext").disabled = !state.fundingReady;
    byId("jobBadge").textContent = "PLAN VERIFIED";
    byId("prepareHire").textContent = "Plan prepared · edit task to prepare again";
    updateReceipt("Verified transaction plan prepared");
    toast(state.fundingReady
      ? "Plan prepared. No transaction has been sent."
      : "Plan prepared for inspection. Sending is locked because the wallet balance is insufficient.");
  } catch (error) {
    toast(`Plan stopped: ${error.message}`, true);
  }
}

async function sendNext() {
  const transaction = currentTransaction();
  if (!transaction || !state.owner || state.active) return;
  state.active = true;
  const button = byId("sendNext");
  button.disabled = true;
  button.textContent = `Confirm ${transaction.label} in wallet…`;
  setStep(transaction.step, "active", "Waiting for your wallet confirmation");
  try {
    const txHash = await ethereum.request({ method: "eth_sendTransaction", params: [walletTransaction(transaction)] });
    setStep(transaction.step, "active", `Submitted · <a href="${EXPLORER}/tx/${txHash}" target="_blank" rel="noreferrer">BscScan ↗</a>`);
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error(`${transaction.label} reverted`);
    state.results.push({ step: transaction.step, tx_hash: txHash, block_number: Number.parseInt(receipt.blockNumber, 16) });
    setStep(transaction.step, "done", `Confirmed · ${short(txHash)}`);
    if (transaction.step === "create_job") {
      state.jobId = extractJobId(receipt);
      byId("jobBadge").textContent = `JOB #${state.jobId}`;
      const followup = await api("/api/live-hire/followup-plan", {
        method: "POST",
        body: JSON.stringify({ buyer: state.owner, skill_id: state.skillId, job_id: state.jobId }),
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
      byId("nextAction").textContent = "Notify the external Agent after escrow funding";
      button.textContent = "Escrow funding complete";
      byId("notifyAgent").disabled = false;
      byId("checkDelivery").disabled = false;
      setStep("agent_delivery", "active", "Funded; Agent notification required");
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

async function notifyAgent() {
  if (!state.jobId) return;
  const button = byId("notifyAgent");
  button.disabled = true;
  button.textContent = "Notifying funded Agent…";
  try {
    state.notifyResult = await api("/api/live-hire/notify", {
      method: "POST",
      body: JSON.stringify({ skill_id: state.skillId, job_id: state.jobId }),
    });
    setStep("agent_delivery", "active", "Agent acknowledged the funded job");
    button.textContent = "Agent notified";
    byId("nextAction").textContent = "Wait for the provider's on-chain submission";
    updateReceipt(`External Agent notified for job #${state.jobId}`);
    toast("The provider acknowledged the funded job. No wallet transaction was sent by this notification.");
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry Agent notification";
    toast(`Agent notification stopped: ${error.message}`, true);
  }
}

async function checkDelivery() {
  if (!state.jobId) return;
  try {
    const status = await api(`/api/live-hire/status/${state.jobId}`);
    updateReceipt(`Job #${state.jobId} is ${status.status}`);
    state.receipt.onchain_status = status;
    byId("receiptJson").textContent = JSON.stringify(state.receipt, null, 2);
    if (status.completed) {
      setStep("agent_delivery", "done", "Delivery recorded on-chain");
      setStep("settle_job", "done", "Completed on-chain");
      byId("nextAction").textContent = "Completed · download the public receipt";
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
      setStep("agent_delivery", "done", `Submitted · deliverable ${short(status.deliverable_hash)}`);
      if (status.can_settle) {
        const settle = await api(`/api/live-hire/settle-plan/${state.jobId}`);
        state.settleTransaction = settle.transaction;
        byId("settleJob").disabled = false;
        setStep("settle_job", "active", `Policy verdict ${status.policy_verdict}`);
        byId("nextAction").textContent = settle.transaction.label;
        toast("Delivery is on-chain and ready for your settlement decision.");
      } else {
        const minutes = Math.max(1, Math.ceil(Number(status.seconds_until_settle || 0) / 60));
        setStep("settle_job", "active", `Review window · about ${minutes} min remaining`);
        toast(`Delivery arrived. Review it while the safety window remains open for about ${minutes} minute(s).`);
      }
    } else {
      toast(`Current on-chain status: ${status.status}.`);
    }
  } catch (error) {
    toast(`Delivery check stopped: ${error.message}`, true);
  }
}

async function sendFinal(transaction, kind) {
  if (!transaction || state.active) return;
  state.active = true;
  const button = kind === "settle" ? byId("settleJob") : byId("refundJob");
  button.disabled = true;
  try {
    const txHash = await ethereum.request({ method: "eth_sendTransaction", params: [walletTransaction(transaction)] });
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error(`${transaction.label} reverted`);
    state.results.push({ step: transaction.step, tx_hash: txHash, block_number: Number.parseInt(receipt.blockNumber, 16) });
    setStep("settle_job", "done", kind === "settle" ? "Provider payment completed" : "Escrow refunded");
    byId("nextAction").textContent = "Completed · download the receipt dossier";
    button.textContent = kind === "settle" ? "Settlement complete" : "Refund complete";
    updateReceipt(`Job #${state.jobId} ${kind === "settle" ? "settled" : "refunded"}`);
    toast(`Job #${state.jobId} ${kind === "settle" ? "settled" : "refunded"} on-chain.`);
  } catch (error) {
    button.disabled = false;
    toast(`${kind === "settle" ? "Settlement" : "Refund"} stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

function downloadReceipt() {
  if (!state.receipt) return;
  const blob = new Blob([`${JSON.stringify(state.receipt, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = `safehire-live-job-${state.jobId || "plan"}.json`;
  link.click();
  URL.revokeObjectURL(link.href);
}

byId("resetTask").addEventListener("click", resetTask);
byId("connectWallet").addEventListener("click", connectWallet);
byId("prepareHire").addEventListener("click", prepareHire);
byId("sendNext").addEventListener("click", sendNext);
byId("notifyAgent").addEventListener("click", notifyAgent);
byId("checkDelivery").addEventListener("click", checkDelivery);
byId("settleJob").addEventListener("click", () => sendFinal(state.settleTransaction, "settle"));
byId("refundJob").addEventListener("click", () => sendFinal(state.refundTransaction, "refund"));
byId("downloadReceipt").addEventListener("click", downloadReceipt);
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

loadQuote();
