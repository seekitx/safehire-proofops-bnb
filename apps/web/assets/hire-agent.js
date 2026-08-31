const CHAIN_ID_HEX = "0x61";
const EXPLORER = "https://testnet.bscscan.com";

const state = {
  owner: null,
  initial: null,
  transactions: [],
  results: [],
  jobId: null,
  active: false,
  settleTransaction: null,
  refundTransaction: null,
};

const byId = (id) => document.getElementById(id);
let toastTimer;

function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 6000);
}

function short(value, head = 10, tail = 8) {
  const text = String(value ?? "");
  return text.length > head + tail + 2 ? `${text.slice(0, head)}…${text.slice(-tail)}` : text;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
  return body;
}

async function ensureTestnet() {
  const chainId = await ethereum.request({ method: "eth_chainId" });
  if (chainId === CHAIN_ID_HEX) return;
  await ethereum.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
}

function setStep(step, status, detail) {
  const row = document.querySelector(`[data-step="${step}"]`);
  if (!row) return;
  row.classList.toggle("active", status === "active");
  row.classList.toggle("done", status === "done");
  row.querySelector("small").innerHTML = detail;
}

async function waitForReceipt(txHash) {
  const deadline = Date.now() + 5 * 60 * 1000;
  while (Date.now() < deadline) {
    const receipt = await ethereum.request({ method: "eth_getTransactionReceipt", params: [txHash] });
    if (receipt) return receipt;
    await new Promise((resolve) => setTimeout(resolve, 3000));
  }
  throw new Error("Receipt was not confirmed within five minutes; check BscScan before retrying.");
}

function nextTransaction() {
  return state.transactions[state.results.length] || null;
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
  const topic = state.initial.job_created_topic.toLowerCase();
  const commerce = state.initial.commerce_address.toLowerCase();
  const log = (receipt.logs || []).find(
    (item) => item.address?.toLowerCase() === commerce && item.topics?.[0]?.toLowerCase() === topic,
  );
  if (!log?.topics?.[1]) throw new Error("JobCreated event was not found in the receipt");
  return Number(BigInt(log.topics[1]));
}

async function connectWallet() {
  if (!window.ethereum) return toast("No EVM wallet was found in Chrome.", true);
  try {
    const accounts = await ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts?.[0]) throw new Error("Wallet returned no account");
    await ensureTestnet();
    state.owner = accounts[0];
    const params = new URLSearchParams(window.location.search);
    const refundJobId = Number.parseInt(params.get("refund_job_id") || "", 10);
    if (Number.isSafeInteger(refundJobId) && refundJobId > 0) {
      const status = await api(`/api/dev/erc8183/status/${refundJobId}`);
      if (!status.can_refund) throw new Error(`Job #${refundJobId} is not eligible for refund`);
      const refund = await api(`/api/dev/erc8183/refund-plan/${refundJobId}`);
      state.jobId = refundJobId;
      state.refundTransaction = refund.transaction;
      byId("buyer").textContent = state.owner;
      byId("connectHireWallet").textContent = short(state.owner);
      byId("hireNetwork").textContent = "BSC Testnet · refund ready";
      byId("hireDot").className = "dot ok";
      byId("quoteStatus").textContent = `Expired job #${refundJobId} · 0.1 U refundable`;
      byId("nextAction").textContent = refund.transaction.label;
      byId("refundJob").disabled = false;
      byId("refundJob").textContent = refund.transaction.label;
      byId("hireNext").disabled = true;
      byId("hireNext").textContent = "Old hire flow closed";
      byId("hireResult").classList.remove("hidden");
      byId("hireResultTitle").textContent = "Expired escrow is refundable.";
      byId("hireResultText").textContent = "The official contract will return exactly 0.1 U to the original buyer wallet.";
      return;
    }
    state.initial = await api("/api/dev/erc8183/initial-plan", {
      method: "POST",
      body: JSON.stringify({ buyer: state.owner }),
    });
    const forceNew = params.get("new_job") === "1";
    const jobIdFromUrl = params.get("job_id");
    const savedJobId = forceNew ? null : (jobIdFromUrl || localStorage.getItem("safehireErc8183JobId"));
    if (forceNew) localStorage.removeItem("safehireErc8183JobId");
    const parsedJobId = Number.parseInt(savedJobId || "", 10);
    if (Number.isSafeInteger(parsedJobId) && parsedJobId > 0) {
      state.jobId = parsedJobId;
      localStorage.setItem("safehireErc8183JobId", String(state.jobId));
      const followup = await api("/api/dev/erc8183/followup-plan", {
        method: "POST",
        body: JSON.stringify({ buyer: state.owner, job_id: state.jobId }),
      });
      state.transactions = followup.transactions;
      setStep("create_job", "done", `Confirmed on-chain · job #${state.jobId}`);
    } else {
      state.transactions = [state.initial.transaction];
    }
    byId("buyer").textContent = state.owner;
    byId("connectHireWallet").textContent = short(state.owner);
    byId("hireNetwork").textContent = "BSC Testnet · ready";
    byId("hireDot").className = "dot ok";
    byId("quoteStatus").textContent = `Verified · 0.1 U · expires ${new Date(state.initial.quote_expires_at * 1000).toLocaleTimeString()}`;
    const next = nextTransaction();
    setStep(next.step, "active", "Ready for wallet confirmation");
    byId("nextAction").textContent = next.label;
    byId("hireNext").textContent = next.label;
    byId("hireNext").disabled = false;
  } catch (error) {
    toast(`Wallet connection stopped: ${error.message}`, true);
  }
}

async function runNext() {
  const transaction = nextTransaction();
  if (!transaction || !state.owner || state.active) return;
  state.active = true;
  const button = byId("hireNext");
  button.disabled = true;
  button.textContent = `Confirm ${transaction.label} in wallet…`;
  setStep(transaction.step, "active", "Waiting for wallet confirmation");
  try {
    const txHash = await ethereum.request({
      method: "eth_sendTransaction",
      params: [walletTransaction(transaction)],
    });
    setStep(transaction.step, "active", `Submitted · <a href="${EXPLORER}/tx/${txHash}" target="_blank" rel="noreferrer">view transaction</a>`);
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error(`${transaction.label} reverted`);
    if (transaction.step === "create_job") {
      state.jobId = extractJobId(receipt);
      localStorage.setItem("safehireErc8183JobId", String(state.jobId));
      const followup = await api("/api/dev/erc8183/followup-plan", {
        method: "POST",
        body: JSON.stringify({ buyer: state.owner, job_id: state.jobId }),
      });
      state.transactions.push(...followup.transactions);
    }
    state.results.push({
      step: transaction.step,
      tx_hash: txHash,
      block_number: Number.parseInt(receipt.blockNumber, 16),
    });
    setStep(transaction.step, "done", `Confirmed · ${short(txHash)}`);
    const upcoming = nextTransaction();
    if (upcoming) {
      setStep(upcoming.step, "active", "Ready for wallet confirmation");
      byId("nextAction").textContent = upcoming.label;
      button.textContent = upcoming.label;
      button.disabled = false;
    } else {
      button.textContent = "0.1 U funding complete";
      byId("nextAction").textContent = "Ask the public Agent to deliver";
      byId("checkDelivery").disabled = false;
      byId("hireResult").classList.remove("hidden");
      byId("hireJson").textContent = JSON.stringify({
        chain_id: 97,
        job_id: state.jobId,
        buyer: state.owner,
        provider: state.initial.provider,
        budget_u: "0.1",
        negotiation_hash: state.initial.negotiation_hash,
        transactions: state.results,
      }, null, 2);
      byId("hireResult").scrollIntoView({ behavior: "smooth", block: "start" });
      toast(`Job #${state.jobId} funded with exactly 0.1 U.`);
    }
  } catch (error) {
    button.disabled = false;
    button.textContent = `Retry ${transaction.label}`;
    setStep(transaction.step, "active", "Stopped before a successful receipt");
    toast(`ERC-8183 action stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

async function checkDelivery() {
  if (!state.jobId) return;
  try {
    const status = await api(`/api/dev/erc8183/status/${state.jobId}`);
    byId("hireResultText").textContent = `On-chain status: ${status.status}.`;
    if (status.can_settle) {
      const settle = await api(`/api/dev/erc8183/settle-plan/${state.jobId}`);
      state.settleTransaction = settle.transaction;
      byId("settleJob").disabled = false;
      const action = status.policy_verdict === "REJECT" ? "return escrow" : "release escrow";
      setStep("settle_job", "active", `Policy verdict: ${status.policy_verdict}; ready to ${action}`);
      toast(`Agent submission has a final ${status.policy_verdict} verdict and is ready to settle.`);
    } else if (status.completed) {
      setStep("settle_job", "done", "Completed on-chain");
      byId("hireResultTitle").textContent = "ERC-8183 hire completed.";
    } else if (status.status === "SUBMITTED" && status.seconds_until_settle > 0) {
      state.settleTransaction = null;
      byId("settleJob").disabled = true;
      const settleAt = new Date(status.settle_after * 1000).toLocaleTimeString();
      const waitMinutes = Math.max(1, Math.ceil(status.seconds_until_settle / 60));
      setStep("settle_job", "active", `Safety review window ends at ${settleAt}`);
      byId("hireResultText").textContent = `Agent submitted on-chain. The 15-minute safety review window is still open; settlement unlocks at ${settleAt}.`;
      toast(`Delivery received. Please wait about ${waitMinutes} minute(s) before settlement.`);
    } else if (status.status === "SUBMITTED" && status.disputed) {
      state.settleTransaction = null;
      byId("settleJob").disabled = true;
      setStep("settle_job", "active", "Disputed; waiting for the policy verdict");
      byId("hireResultText").textContent = "Agent submitted on-chain, but the job is disputed. Settlement stays locked until the policy returns a final verdict.";
      toast("This job is disputed and cannot be settled yet.", true);
    } else {
      toast(`Current job status: ${status.status}. Try again after Agent delivery.`);
    }
  } catch (error) {
    toast(`Could not read job status: ${error.message}`, true);
  }
}

async function settleJob() {
  if (!state.settleTransaction || state.active) return;
  state.active = true;
  const button = byId("settleJob");
  button.disabled = true;
  button.textContent = "Confirm settlement in wallet…";
  try {
    const txHash = await ethereum.request({
      method: "eth_sendTransaction",
      params: [walletTransaction(state.settleTransaction)],
    });
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error("Settlement reverted");
    state.results.push({
      step: "settle_job",
      tx_hash: txHash,
      block_number: Number.parseInt(receipt.blockNumber, 16),
    });
    setStep("settle_job", "done", `Confirmed · ${short(txHash)}`);
    byId("hireResultTitle").textContent = "ERC-8183 hire completed.";
    byId("hireResultText").textContent = "The verified delivery was settled and the 0.1 U escrow was released to the Agent provider.";
    byId("hireJson").textContent = JSON.stringify({
      chain_id: 97,
      job_id: state.jobId,
      buyer: state.owner,
      provider: state.initial.provider,
      budget_u: "0.1",
      negotiation_hash: state.initial.negotiation_hash,
      transactions: state.results,
      completed: true,
    }, null, 2);
    button.textContent = "Settlement complete";
    toast(`Job #${state.jobId} completed on-chain.`);
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry settlement";
    toast(`Settlement stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

async function refundJob() {
  if (!state.refundTransaction || state.active) return;
  state.active = true;
  const button = byId("refundJob");
  button.disabled = true;
  button.textContent = "Confirm refund in wallet…";
  try {
    const txHash = await ethereum.request({
      method: "eth_sendTransaction",
      params: [walletTransaction(state.refundTransaction)],
    });
    const receipt = await waitForReceipt(txHash);
    if (receipt.status !== "0x1") throw new Error("Refund reverted");
    byId("hireResultTitle").textContent = "Expired escrow refunded.";
    byId("hireResultText").textContent = "The 0.1 U escrow was returned to the original buyer wallet.";
    byId("hireJson").textContent = JSON.stringify({
      chain_id: 97,
      job_id: state.jobId,
      action: "claim_refund",
      tx_hash: txHash,
      block_number: Number.parseInt(receipt.blockNumber, 16),
      refunded_u: "0.1",
    }, null, 2);
    button.textContent = "Refund complete";
    toast(`Job #${state.jobId} refunded 0.1 U.`);
  } catch (error) {
    button.disabled = false;
    button.textContent = "Retry expired escrow refund";
    toast(`Refund stopped: ${error.message}`, true);
  } finally {
    state.active = false;
  }
}

byId("connectHireWallet").addEventListener("click", connectWallet);
byId("hireNext").addEventListener("click", runNext);
byId("checkDelivery").addEventListener("click", checkDelivery);
byId("settleJob").addEventListener("click", settleJob);
byId("refundJob").addEventListener("click", refundJob);

if (window.ethereum?.on) {
  ethereum.on("accountsChanged", () => location.reload());
  ethereum.on("chainChanged", () => location.reload());
}
