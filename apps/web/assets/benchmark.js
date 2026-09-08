const byId = (id) => document.getElementById(id);
const criteria = ["correctness", "completeness", "risk_awareness", "actionability", "evidence_quality"];
let task = null;
let startedAt = null;
let startedClock = null;
let timerHandle = null;
let agentRaw = null;
let manualRaw = null;
let packet = null;
let toastTimer = null;
const uiTest = new URLSearchParams(location.search).get('ui_test') === '1';
if (uiTest) byId('manualAttestation').parentElement.lastChild.textContent = '这是自动化页面检查，不作为真人实验。';
window.addEventListener('beforeunload', event => {
  if (startedAt && !byId('finishManual').disabled) { event.preventDefault(); event.returnValue = ''; }
});

function toast(message, error = false) {
  const element = byId("toast");
  element.textContent = message;
  element.classList.toggle("error", error);
  element.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => element.classList.remove("show"), 5500);
}

function downloadJson(name, value) {
  const blob = new Blob([`${JSON.stringify(value, null, 2)}\n`], { type: "application/json" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = name;
  link.click();
  URL.revokeObjectURL(link.href);
}

async function loadJsonFile(file) {
  if (!file) throw new Error("Choose a JSON file first");
  return JSON.parse(await file.text());
}

function elapsedSeconds() {
  return startedClock === null ? 0 : (performance.now() - startedClock) / 1000;
}

function renderTimer() {
  const elapsed = elapsedSeconds();
  const minutes = Math.floor(elapsed / 60).toString().padStart(2, "0");
  const seconds = (elapsed % 60).toFixed(1).padStart(4, "0");
  byId("elapsedTime").textContent = `${minutes}:${seconds}`;
}

async function loadTask() {
  task = null;
  const taskId = byId("taskSelect").value;
  const response = await fetch(`/api/evidence/termix/tasks/${encodeURIComponent(taskId)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  if (byId("taskSelect").value !== taskId) return;
  task = payload;
  byId("taskBrief").textContent = "题目已准备好。填写姓名后，点“开始计时”才会显示题目。";
  byId("manualOutput").value = "";
  byId("manualOutput").disabled = true;
}

function readableInputs(input) {
  const labels = {collateral_usd: '抵押品价值（美元）', debt_usd: '债务（美元）', liquidation_threshold: '加权清算阈值（小数）', alert_health_factor: '提醒线', target_health_factor: '目标健康系数', current_price: '当前价格', lower_price: '价格下界', upper_price: '价格上界', levels: '档数', capital_usd: '资金（美元）', max_drawdown_pct: '设置的最大回撤（%）', horizon_days: '天数', protocol: '市场', gross_apy: '年收益率 APY（%）', risk_score: '假设风险分', tvl_usd: '未读取的规模占位值', transaction_cost_usd: '假设成本（美元）'};
  return Object.entries(input).filter(([key]) => key !== 'source').map(([key, value]) =>
    key === 'candidates' ? value.map(row => readableInputs(row)).join('\n\n') : `${labels[key] || key}：${value}`).join('\n');
}

function canonical(value) {
  if (Array.isArray(value)) return value.map(canonical);
  if (value && typeof value === 'object') return Object.fromEntries(Object.keys(value).sort().map(key => [key, canonical(value[key])]));
  return value;
}

function startTimer() {
  if (!task) return toast("Task brief is not loaded.", true);
  const operator = byId("operatorName").value.trim();
  if (!operator) return toast("请先填写实际操作人的姓名或公开昵称。", true);
  startedAt = new Date();
  startedClock = performance.now();
  byId("taskSelect").disabled = true;
  byId("operatorName").disabled = true;
  byId("taskBrief").textContent = task.manual_brief_zh ? `${task.title_zh}\n\n${task.manual_brief_zh}\n\n数据读取时间：${task.source_snapshot.observed_at}\n\n计算数据：\n${readableInputs(task.agent_request.input)}` : JSON.stringify(task, null, 2);
  byId("manualOutput").disabled = false;
  byId("manualOutput").focus();
  byId("startTimer").disabled = true;
  byId("finishManual").disabled = false;
  byId("timerState").textContent = "RUNNING";
  timerHandle = setInterval(renderTimer, 100);
  renderTimer();
}

function finishManual() {
  const answer = byId("manualOutput").value.trim();
  if (!answer) return toast("请先写下完整答案，再结束计时。", true);
  if (!byId("manualAttestation").checked || !byId("manualTools").value.trim()) return toast("请填写实际使用的工具，并勾选亲自完成的声明。", true);
  const cost = Number(byId("manualCost").value);
  if (!Number.isFinite(cost) || cost < 0) return toast("Enter a valid non-negative cost.", true);
  const duration = elapsedSeconds();
  clearInterval(timerHandle);
  renderTimer();
  const finishedAt = new Date();
  const record = {
    schema_version: "safehire-termix-manual-v2",
    evidence_mode: uiTest ? "ui_verification_not_human" : "human_timed_manual_run",
    task_id: task.task_id,
    task_snapshot: task,
    operator: byId("operatorName").value.trim(),
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    duration_seconds: Number(duration.toFixed(3)),
    tools_used: byId("manualTools").value.trim(),
    cost: { amount: cost, currency: byId("manualCurrency").value.trim() || "USD" },
    output: answer,
    attestations: {
      no_safehire_agent_called: !uiTest,
      no_pause_available_in_timer: true,
      complete_output_preserved: true,
    },
  };
  byId("finishManual").disabled = true;
  byId("manualOutput").disabled = true;
  byId("timerState").textContent = "RECORDED";
  downloadJson(`${task.task_id}-manual-output.json`, record);
  toast("人工记录已下载。请保留原文件，然后告诉我已完成。");
}

function renderScores() {
  byId("scoreGrid").innerHTML = ["A", "B"].map((side) => `
    <section class="score-card"><h3>Output ${side}</h3>${criteria.map((criterion) => `
      <label>${criterion.replaceAll("_", " ")}<input data-score="${side}" data-criterion="${criterion}" type="number" min="1" max="5" step="1" required /></label>`).join("")}</section>`).join("");
}

async function maybeEnablePacket() {
  try {
    agentRaw = await loadJsonFile(byId("agentFile").files[0]);
    manualRaw = await loadJsonFile(byId("manualFile").files[0]);
    byId("buildPacket").disabled = false;
  } catch (_error) {
    byId("buildPacket").disabled = true;
  }
}

function answerContent(raw) {
  const invocation = raw.response?.result?.agent_result;
  if (invocation) return {result: invocation.result, risk_checks: invocation.risk_checks, source_labels: invocation.source_labels};
  if (raw.output !== undefined) return raw.output;
  if (raw.answer !== undefined) return raw.answer;
  throw new Error("Unrecognised output format. Preserve raw files and supply an answer envelope with task_id and output.");
}

function buildPacket() {
  if (manualRaw?.evidence_mode !== "human_timed_manual_run") return toast("需要真实人工操作记录，页面测试不能参加比较。", true);
  if (!agentRaw?.task_id || agentRaw.task_id !== manualRaw?.task_id) return toast("Both outputs must have the same explicit task_id.", true);
  if (!agentRaw.task_snapshot || !manualRaw.task_snapshot || JSON.stringify(canonical(agentRaw.task_snapshot)) !== JSON.stringify(canonical(manualRaw.task_snapshot))) return toast("两份文件的完整题目和输入不一致，不能配对比较。", true);
  let agentAnswer, manualAnswer;
  try { agentAnswer = answerContent(agentRaw); manualAnswer = answerContent(manualRaw); }
  catch (error) { return toast(error.message, true); }
  const taskId = String(agentRaw.task_id || manualRaw.task_id || task?.task_id || "comparison");
  const agentIsA = crypto.getRandomValues(new Uint8Array(1))[0] % 2 === 0;
  const packetId = crypto.randomUUID();
  const outputs = agentIsA ? { A: agentAnswer, B: manualAnswer } : { A: manualAnswer, B: agentAnswer };
  const blindPacket = { schema_version: "safehire-termix-blind-packet-v2", packet_id: packetId, task_id: taskId, outputs };
  const secretKey = {
    schema_version: "safehire-termix-blind-key-v2",
    packet_id: packetId,
    task_id: taskId,
    original_outputs: {agent: agentRaw, manual: manualRaw},
    mapping: agentIsA ? { A: "agent", B: "manual" } : { A: "manual", B: "agent" },
    warning: "Do not share this mapping with the reviewer until scoring is complete.",
  };
  downloadJson(`${taskId}-blind-review-packet.json`, blindPacket);
  downloadJson(`${taskId}-blind-review-secret-key.json`, secretKey);
  toast("Two files downloaded. Send only the blind packet to the reviewer.");
}

async function loadPacket() {
  try {
    const value = await loadJsonFile(byId("packetFile").files[0]);
    if (!value.outputs?.A || !value.outputs?.B || !value.packet_id) throw new Error("This is not a valid blind packet");
    packet = value;
    byId("outputA").textContent = JSON.stringify(value.outputs.A, null, 2);
    byId("outputB").textContent = JSON.stringify(value.outputs.B, null, 2);
    byId("blindOutputs").hidden = false;
    byId("scoreGrid").hidden = false;
    byId("downloadReview").disabled = false;
  } catch (error) {
    packet = null;
    byId("downloadReview").disabled = true;
    toast(error.message, true);
  }
}

function downloadReview() {
  const reviewer = byId("reviewerName").value.trim();
  if (!reviewer) return toast("Enter the real reviewer name first.", true);
  if (!byId("reviewAttestation").checked || !byId("reviewRationale").value.trim()) return toast("Confirm the review and explain your scores.", true);
  const scores = { A: {}, B: {} };
  for (const input of document.querySelectorAll("[data-score]")) {
    const value = Number(input.value);
    if (!Number.isInteger(value) || value < 1 || value > 5) return toast("Every score must be a whole number from 1 to 5.", true);
    scores[input.dataset.score][input.dataset.criterion] = value;
  }
  const review = {
    schema_version: "safehire-termix-blind-review-v2",
    packet_id: packet.packet_id,
    task_id: packet.task_id,
    reviewer,
    reviewed_at: new Date().toISOString(),
    rationale: byId("reviewRationale").value.trim(),
    rubric: "1-5 each: correctness, completeness, risk awareness, actionability, evidence quality",
    scores,
    totals: {
      A: Object.values(scores.A).reduce((sum, value) => sum + value, 0),
      B: Object.values(scores.B).reduce((sum, value) => sum + value, 0),
    },
    attestations: { mapping_not_seen_before_scoring: true, outputs_reviewed_in_full: true },
  };
  downloadJson(`${packet.task_id}-blind-review.json`, review);
  toast("Blind review downloaded. The preparer can now merge it with the secret key.");
}

byId("taskSelect").addEventListener("change", () => loadTask().catch((error) => toast(error.message, true)));
byId("startTimer").addEventListener("click", startTimer);
byId("finishManual").addEventListener("click", finishManual);
byId("agentFile").addEventListener("change", maybeEnablePacket);
byId("manualFile").addEventListener("change", maybeEnablePacket);
byId("buildPacket").addEventListener("click", buildPacket);
byId("packetFile").addEventListener("change", loadPacket);
byId("downloadReview").addEventListener("click", downloadReview);
const requestedTask = new URLSearchParams(location.search).get('task');
if ([...byId('taskSelect').options].some(option => option.value === requestedTask)) byId('taskSelect').value = requestedTask;
renderScores();
loadTask().catch((error) => toast(error.message, true));
