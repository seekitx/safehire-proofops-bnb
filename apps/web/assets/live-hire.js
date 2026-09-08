// Keep large JSON integers as exact numeric tokens, distinct from decimal strings.
const responseBytes = new WeakMap();
const taskJSON = {
  parse(text) {
    return JSON.parse(text, (key, value, context) => {
      if (key !== 'liquidity_raw' || typeof value !== 'number') return value;
      const source = context?.source || (Number.isSafeInteger(value) ? String(value) : '');
      if (!JSON.rawJSON || !/^[1-9][0-9]*$/.test(source)) {
        throw new Error('This browser cannot preserve large LP numbers. Use a current Chrome or Edge.');
      }
      return JSON.rawJSON(source);
    });
  },
  stringify: (value, replacer = null, space) => JSON.stringify(value, replacer, space)
};

"use strict";

const CHAIN_ID_HEX = "0x38";
const EXPLORER = "https://bscscan.com";
const expectedPrice = () => BigInt(state.quotePayload?.quote?.price || ([269224,269226,269228].includes(state.agentTokenId) ? '500000000000000000' : '100000000000000000'));
const priceLabel = () => `${Number(expectedPrice()) / 1e18} U`;
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
  arenaTask: null,
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
  const raw = await response.text();
  const body = taskJSON.parse(raw);
  if (body && typeof body === "object") responseBytes.set(body, raw);
  if (!response.ok) throw new Error(body.detail || body.message || `HTTP ${response.status}`);
  return body;
}

function selectedInput() {
  if ([269228,269226].includes(state.agentTokenId)) {
    if (state.calculatorSourceRequired && !state.calculatorInput) throw new Error('实时来源尚未读取成功；请重试，或明确选择改用手填值');
    if (state.calculatorSourceAt && Date.now()/1000-state.calculatorSourceAt>600) throw new Error('来源快照已超过 10 分钟，请重新读取');
    if (state.calculatorInput) return structuredClone(state.calculatorInput);
    if (state.agentTokenId === 269228 && byId('calcCollateral')) return {
      collateral:{collateral_USD:{amount:Number(byId('calcCollateral').value),liqThreshold:Number(byId('calcThreshold').value)}},
      debt:{debt_USD:Number(byId('calcDebt').value)},prices:{collateral_USD:1,debt_USD:1},alertHF:1.5,criticalHF:1.1};
    if (state.agentTokenId === 269226 && byId('calcCapital')) return {
      pools:{candidate_a:{apyPct:Number(byId('calcRateA').value)},candidate_b:{apyPct:Number(byId('calcRateB').value)}},
      capitalUsd:Number(byId('calcCapital').value),maxPerPoolPct:60};
  }
  if (state.agentTokenId === 269224 && byId('gridPrice')) {
    return {price: Number(byId('gridPrice').value), budgetUsd: Number(byId('gridBudget').value),
      levels: Number(byId('gridLevels').value), spanPct: Number(byId('gridSpan').value)};
  }
  let value;
  try {
    value = taskJSON.parse(byId("taskInput").value);
  } catch (error) {
    throw new Error(`Task JSON is invalid: ${error.message}`);
  }
  if (!value || Array.isArray(value) || typeof value !== "object") {
    throw new Error("Task input must be a JSON object");
  }
  return value;
}

function calculatorForm() {
  const token = state.agentTokenId;
  if (![269228, 269226].includes(token)) return;
  const form = document.createElement('fieldset');
  const health = token === 269228;
  form.innerHTML = `<legend>${health ? '借贷健康计算' : '收益分配计算'} · 单次分析，不执行交易</legend>
    ${health ? '<label>抵押品美元价值<input id="calcCollateral" type="number" min="0.01" step="any" value="20000"></label><label>加权清算阈值（0–1）<input id="calcThreshold" type="number" min="0.0001" max="1" step="any" value="0.8"></label><label>债务美元价值<input id="calcDebt" type="number" min="0.01" step="any" value="10000"></label><label>读取真实 Venus Core 账户<input id="calcAccount" placeholder="公开账户地址 0x…" maxlength="42"></label>' : '<label>计划分配资金 / 美元<input id="calcCapital" type="number" min="0.01" max="1000000000" step="any" value="10000"></label><label>候选 A 年化 / %<input id="calcRateA" type="number" min="0" max="1000" step="any" value="6.1"></label><label>候选 B 年化 / %<input id="calcRateB" type="number" min="0" max="1000" step="any" value="4.2"></label>'}
    <p>默认值仅是假设练习。0.50 U 买一次供应商计算；不含资金迁移、交易、持续监控或收益保证。首次真实交付及内容质量尚待验证。离站提醒需要在工作台另行开启。</p>
    <label><input id="calcSourceConsent" type="checkbox">同意读取公开链上数据；最终确认付款后，任务输入会公开写入链上。</label>
    <button id="calcLoadSource" type="button">读取当前数据并用于本次任务</button>
    <button id="calcUseManual" type="button">改用上方手填值</button>
    <button id="calcDownloadSource" type="button" disabled>下载本次来源原文</button>
    <p id="calcSourceStatus">当前使用假设手填值；尚未读取实时来源。</p><pre id="calcSourcePreview" style="white-space:pre-wrap;max-height:240px;overflow:auto"></pre>`;
  byId('taskInput').before(form);
  byId('taskInput').hidden = true;
  byId('resetTask').hidden = true;
  let source = null;
  const reset = () => {
    state.calculatorInput = null; state.calculatorSourceRequired = false; state.calculatorSourceAt = null; source = null;
    byId('calcSourceStatus').textContent = '已改用手填值；这些值未获得实时来源认证。';
    byId('calcSourcePreview').textContent = '';
    byId('calcDownloadSource').disabled = true;
  };
  form.querySelectorAll('input[type="number"]').forEach(input => input.addEventListener('input', reset));
  byId('calcAccount')?.addEventListener('input', reset);
  byId('calcUseManual').onclick = reset;
  byId('calcLoadSource').onclick = async () => {
    const button = byId('calcLoadSource');
    if (!byId('calcSourceConsent').checked) return toast('请先勾选公开数据读取说明', true);
    button.disabled = true; reset(); state.calculatorSourceRequired = true;
    byId('calcSourceStatus').textContent = '正在读取同一区块的数据，请稍候…';
    try {
      source = await api('/api/workspace/calculator-source', {method:'POST',body:JSON.stringify({
        token_id:token, account:health ? byId('calcAccount').value.trim() : null,
        capital:health ? 10000 : Number(byId('calcCapital').value), consent:true})});
      state.calculatorInput = source.task_input; state.calculatorSourceAt = source.observation.block_timestamp;
      byId('calcSourceStatus').textContent = `本次任务改用区块 ${source.observation.block_number} 的数据，读取于 ${source.observation.observed_at}。${source.boundary}`;
      byId('calcSourcePreview').textContent = JSON.stringify(source.task_input,null,2);
      byId('calcDownloadSource').disabled = false;
    } catch(error) { byId('calcSourceStatus').textContent = error.message; toast(error.message,true); }
    finally {button.disabled=false;}
  };
  byId('calcDownloadSource').onclick = () => {
    if (!source) return;
    const url=URL.createObjectURL(new Blob([JSON.stringify(source,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download=`safehire-calculator-source-${token}-${source.observation.block_number}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  };
}

function taskExample() {
  if (state.agentTokenId === 269228) return {collateral:{ETH:{amount:10,liqThreshold:0.8}},debt:{USDT:10000},prices:{ETH:2000,USDT:1}};
  if (state.agentTokenId === 269226) return {pools:{example_a:{apyPct:6.1},example_b:{apyPct:4.2}},capitalUsd:10000,maxPerPoolPct:60};
  if (state.agentTokenId === 269224) return {price: 750, budgetUsd: 1000, levels: 5, spanPct: 2};
  const value = structuredClone(examples[state.skillId]);
  if (state.skillId === "health_factor" && state.owner) value.address = state.owner;
  return value;
}

function resetTask() {
  if (state.arenaTask) {
    byId("taskInput").value = taskJSON.stringify(state.arenaTask.inputs, null, 2);
    byId("taskInput").readOnly = true;
    byId("resetTask").disabled = true;
    byId("prepareNote").textContent = "Frozen Arena task attached. Inputs cannot be edited here; return to Arena to create a changed task. Fresh signed terms must include the full task before any wallet action.";
    return;
  }
  byId("taskInput").value = taskJSON.stringify(taskExample(), null, 2);
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

async function registerServerFollowup(jobId) {
  if (!byId('serverFollowup')?.checked) return;
  try {
    let credential = JSON.parse(localStorage.getItem('safehire-workspace-v1') || 'null');
    if (!credential) {
      credential = await api('/api/workspace/spaces', {method:'POST', body:'{}'});
      localStorage.setItem('safehire-workspace-v1', JSON.stringify(credential));
    }
    await api(`/api/workspace/spaces/${credential.space_id}/watches`, {
      method:'POST', headers:{Authorization:`Bearer ${credential.token}`},
      body:JSON.stringify({kind:'order', job_id:jobId, notify_provider:true, consent:true})
    });
  } catch (error) { toast(`订单已在链上；服务器跟进未保存：${error.message}。请保留订单号。`, true); }
}

function persistJob() {
  if (!state.jobId) return;
  void registerServerFollowup(state.jobId);
  const record = {
    job_id: state.jobId,
    skill_id: state.skillId,
    agent_token_id: state.agentTokenId,
    owner: state.owner,
    saved_at: new Date().toISOString(),
  };
  localStorage.setItem(STORAGE_KEY, taskJSON.stringify(record));
  try {
    const jobs = JSON.parse(localStorage.getItem('safehire-my-jobs') || '[]');
    localStorage.setItem('safehire-my-jobs', JSON.stringify([record, ...jobs.filter(j => j.job_id !== record.job_id)].slice(0, 100)));
  } catch (_) { /* Chain and URL remain recovery sources. */ }
  const url = new URL(location.href);
  url.searchParams.set("job_id", String(state.jobId));
  url.searchParams.set("skill_id", state.skillId);
  if (state.agentTokenId) url.searchParams.set("agent_token_id", String(state.agentTokenId));
  history.replaceState(null, "", url);
}

function savedJob() {
  const params = new URLSearchParams(location.search);
  const queryJob = Number(params.get("job_id") || 0);
  if (params.has('job_id')) return Number.isSafeInteger(queryJob) && queryJob > 0 ? queryJob : null;
  // An explicit service link is a new purchase, even when the browser remembers an old job.
  if (params.has('agent_token_id') || params.has('skill_id')) return null;
  try {
    const record = taskJSON.parse(localStorage.getItem(STORAGE_KEY) || "null");
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
  const uReady = u >= expectedPrice();
  byId("bnbBalance").parentElement.classList.toggle("ready", gasReady);
  byId("uBalance").parentElement.classList.toggle("ready", uReady);
  byId("gasReadiness").textContent = gasReady ? "Gas available" : "Needs BNB gas";
  byId("uReadiness").textContent = uReady ? `${priceLabel()} available` : "Insufficient for hire";
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
  if (params.get("job_id")) {
    byId("quoteState").textContent = "恢复已有订单：连接钱包后读取链上记录，无需新报价";
    return;
  }
  const requested = params.get("skill_id") || "grid_plan";
  state.skillId = SKILLS.has(requested) ? requested : "grid_plan";
  const token = Number(params.get("agent_token_id") || 0);
  state.agentTokenId = Number.isSafeInteger(token) && token > 0 ? token : null;
  if (params.get("arena") === "1") {
    try {
      const handoff = taskJSON.parse(sessionStorage.getItem("safehire-arena-handoff-v1"));
      const expectedRef = `56:${state.agentTokenId}:${state.skillId}`;
      const categories = {rebalance_plan: 'rebalancing', grid_plan: 'grid_trading', yield_plan: 'yield_optimisation', health_factor: 'health_factor_monitoring'};
      if (!handoff?.task || handoff.agent_ref !== expectedRef || handoff.task.category !== categories[state.skillId]) throw new Error('Saved task and selected provider do not match.');
      state.arenaTask = handoff.task;
    } catch (error) {
      byId("quoteState").textContent = "TASK UNAVAILABLE";
      throw new Error(`Return to Arena and open the saved task again: ${error.message}`);
    }
  }
  resetTask();
  calculatorForm();
  if (state.agentTokenId === 269224) {
    const form = document.createElement('fieldset');
    form.innerHTML = '<legend>网格计算参数（不会实际下单）</legend><label>参考价格<input id="gridPrice" type="number" min="0.00000001" step="any" value="750"></label><label>假设资金 / 美元<input id="gridBudget" type="number" min="0.01" step="any" value="1000"></label><label>每侧档数<input id="gridLevels" type="number" min="1" max="50" value="5"></label><label>半宽 / %<input id="gridSpan" type="number" min="0.01" max="99" step="any" value="2"></label><p>参考价格与资金由你提供，默认值是假设示例。服务交付价格表，不会管理订单或执行止损。</p>';
    byId('taskInput').before(form);
    byId('taskInput').hidden = true;
    byId('resetTask').hidden = true;
  }
  try {
    const payload = await api("/api/live-market/quote", {
      method: "POST",
      body: taskJSON.stringify({ skill_id: state.skillId, agent_token_id: state.agentTokenId }),
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
    byId("prepareHire").textContent = `Prepare fresh signed ${priceLabel()} hire`;
    byId("prepareNote").textContent = state.writeEnabled
      ? state.fundingReady
        ? "Balances are sufficient. Preparing remains read-only and verifies a fresh provider signature."
        : "You can inspect the signed plan, but sending stays locked until this wallet has BNB gas and the quoted U amount."
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
    journey: journeyEvent("receipt_viewed"),
    agent_notification: state.notifyResult,
    delivery: state.delivery,
    observed_at: new Date().toISOString(),
    boundary:
      "This browser activity draft is not the server-verified paid-delivery dossier. Use the verified download after completion.",
  };
  byId("receiptPanel").hidden = false;
  byId("receiptTitle").textContent = title;
  byId("receiptJson").textContent = taskJSON.stringify(state.receipt, null, 2);
}

async function prepareHire() {
  journeyEvent("prepare_requested");
  if (!state.owner || !state.quotePayload || !state.writeEnabled) return;
  if (state.quotePayload.agent?.requires_arena && !state.arenaTask) {
    return toast('This LP service requires a frozen LP range task. Open Arena, select LP ranges and carry the saved task here.', true);
  }
  if (!byId("riskConfirm").checked) {
    return toast("Confirm the BSC Mainnet risk statement first.", true);
  }
  try {
    const taskInput = selectedInput();
    state.plan = await api("/api/live-hire/prepare", {
      method: "POST",
      body: taskJSON.stringify({
        buyer: state.owner,
        skill_id: state.skillId,
        agent_token_id: state.agentTokenId,
        task_input: taskInput,
        ...(state.arenaTask ? {arena_task: state.arenaTask} : {}),
      }),
    });
    showQuote(state.plan);
    byId("escrowTiming").textContent = `Delivery estimate: ${Math.ceil(state.plan.timeline.estimated_completion_seconds / 60)} minutes. On-chain dispute window: ${(state.plan.timeline.dispute_window_seconds / 86400).toFixed(2)} days. Job expires ${unixTime(state.plan.expires_at)}. Delivery does not mean immediate payment release.`;
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
    journeyEvent("transaction_confirmed",{step:transaction.step,tx_hash:txHash,gas_used_raw:receipt.gasUsed,effective_gas_price_raw:receipt.effectiveGasPrice});
    setStep(transaction.step, "done", `Confirmed · ${short(txHash)}`);
    if (transaction.step === "create_job") {
      state.jobId = extractJobId(receipt);
      try {
        const pending=JSON.parse(localStorage.getItem('safehire-hire-journey-v1:draft')||'null');
        if(pending){pending.job_id=state.jobId;localStorage.setItem('safehire-hire-journey-v1:'+state.jobId,JSON.stringify(pending));localStorage.removeItem('safehire-hire-journey-v1:draft');}
      } catch (_) { /* Never block chain recovery on browser storage. */ }
      persistJob();
      byId("jobBadge").textContent = `JOB #${state.jobId}`;
      const followup = await api("/api/live-hire/followup-plan", {
        method: "POST",
        body: taskJSON.stringify({ buyer: state.owner, job_id: state.jobId }),
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
    state.arenaTask = status.task_spec.arena_task || null;
    state.skillId = status.task_spec.service;
    state.agentTokenId = Number(status.task_spec.erc8004_token_id);
    byId("taskInput").value = taskJSON.stringify(status.task_spec.task_input, null, 2);
    state.calculatorInput = [269228,269226].includes(state.agentTokenId) ? status.task_spec.task_input : null;
    byId("jobBadge").textContent = `JOB #${jobId} · ${status.status}`;
    byId("resumeState").hidden = false;
    byId("resumeState").textContent =
      `Recovered job #${jobId} from BSC. Browser memory is not trusted; the next action was rebuilt from chain state.`;
    resetSteps();
    setStep("create_job", "done", "Recovered from on-chain job");
    persistJob();

    if (status.status === "OPEN") {
      if (status.open_progress?.policy_registered) setStep("register_job", "done", "Confirmed on-chain");
      if (BigInt(status.budget_raw || 0) === BigInt(status.price_raw || expectedPrice())) setStep("set_budget", "done", "Confirmed on-chain");
      if (status.open_progress?.exact_allowance) setStep("approve_u", "done", "Exact allowance confirmed");
      const followup = await api("/api/live-hire/followup-plan", {
        method: "POST",
        body: taskJSON.stringify({ buyer: state.owner, job_id: jobId }),
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
      body: taskJSON.stringify({ job_id: state.jobId }),
    });
    setStep("agent_delivery", "active", "Provider received notification; work has not been verified");
    button.textContent = state.notifyResult.status === "accepted" ? "Provider notified" : state.notifyResult.status;
    byId("nextAction").textContent = "Acknowledgement is not proof that work started. Check on-chain delivery; do not pay again.";
    updateReceipt(`Provider notification for job #${state.jobId}`);
    toast("Notification sent without another wallet transaction. Provider execution is still unverified.");
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
  if (!delivery.acceptance) {
    let box = byId('semanticAcceptance');
    if (!box) { box = document.createElement('p'); box.id = 'semanticAcceptance'; byId('deliveryContent').before(box); }
    box.textContent = '交付文件与链上记录一致，但此类结果尚未通过内容验收。请逐项核对输入、计算和用途，再决定接受或争议。';
    byId('gridResultSummary')?.remove();
  }
  if (delivery.acceptance) {
    let box = byId('semanticAcceptance');
    if (!box) { box = document.createElement('p'); box.id = 'semanticAcceptance'; byId('deliveryContent').before(box); }
    box.textContent = delivery.acceptance.passed ? '计算验收通过：参数、档数、价格、数量与总金额一致。不代表盈利或实际交易。' : `计算验收未通过：${delivery.acceptance.failures.join('; ')}`;
  }
  if (delivery.acceptance?.passed) {
    const grid = JSON.parse(verification.content);
    let summary = byId('gridResultSummary');
    if (!summary) { summary = document.createElement('div'); summary.id='gridResultSummary'; byId('deliveryContent').before(summary); }
    summary.innerHTML = `<h3>你买到的网格计算结果</h3><p>参考价格 ${escapeHtml(grid.mark)}；假设总资金 ${escapeHtml(grid.budgetUsd)} 美元；每侧 ${escapeHtml(grid.levelsPerSide)} 档。</p><table><thead><tr><th>方向</th><th>价格</th><th>分配金额</th><th>计算数量</th></tr></thead><tbody>${[...grid.buys,...grid.sells].map(r=>`<tr><td>${r.side==='buy'?'买入':'卖出'}</td><td>${escapeHtml(r.price)}</td><td>${escapeHtml(r.sizeUsd)}</td><td>${escapeHtml(r.amount)}</td></tr>`).join('')}</tbody></table><p>这是按你提供的输入计算的价格表，未执行交易；费用、滑点、订单管理与止损不包含在这份服务中。</p>`;
  }
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
  journeyEvent("delivery_checked",{job_id:state.jobId,arithmetic_acceptance:delivery.acceptance?.passed??null});
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
    if (status.status === "FUNDED") {
      const deadline = new Date(status.expired_at * 1000).toLocaleString();
      byId("jobBadge").textContent = `JOB #${state.jobId} · FUNDED`;
      setStep("agent_delivery", "active", "Funds in escrow; no result submitted");
      byId("nextAction").textContent = `Waiting on the provider. No additional payment needed. If no result arrives, refund is available after ${deadline}. Internal provider progress is unavailable.`;
      updateReceipt(`Job #${state.jobId} · checked ${new Date().toLocaleString()} · no delivery yet`);
      return toast(`Funds are in escrow; the provider has not submitted a result. No need to pay again. Expiry refund: ${deadline}.`);
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
      body: taskJSON.stringify({ buyer: state.owner, job_id: state.jobId }),
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
  const blob = new Blob([responseBytes.get(payload) || `${taskJSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
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

// Client timestamps are an audit aid, not trusted chain time or an efficiency claim.
function journeyEvent(stage, detail = {}) {
  try {
    const job=state.jobId||Number(new URLSearchParams(location.search).get('job_id'))||null;
    const key='safehire-hire-journey-v1:'+String(job||'draft');
    let value=JSON.parse(localStorage.getItem(key)||'null');
    if(!value || (value.job_id && value.job_id!==job) || (!job && (value.agent_token_id!==state.agentTokenId || Date.now()-Date.parse(value.started_at)>86400000))) value={schema:'safehire-hire-journey/1',started_at:new Date().toISOString(),job_id:job,agent_token_id:state.agentTokenId,events:[],timing_basis:'client_reported_wall_clock',coverage:job?'recovered_order_partial':'hire_page_to_delivery',independent_verification:false};
    value.events.push({stage,at:new Date().toISOString(),...detail});value.events=value.events.slice(-100);
    localStorage.setItem(key,JSON.stringify(value));return value;
  } catch (_) { return {recording_unavailable:true}; }
}
journeyEvent('page_opened');
