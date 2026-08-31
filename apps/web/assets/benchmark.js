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
  const taskId = byId("taskSelect").value;
  const response = await fetch(`/api/evidence/termix/tasks/${encodeURIComponent(taskId)}`);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
  task = payload;
  byId("taskBrief").textContent = "Task brief is locked. Start the timer to reveal it.";
  byId("manualOutput").value = "";
  byId("manualOutput").disabled = true;
}

function startTimer() {
  if (!task) return toast("Task brief is not loaded.", true);
  const operator = byId("operatorName").value.trim();
  if (!operator) return toast("Enter the real manual operator name first.", true);
  startedAt = new Date();
  startedClock = performance.now();
  byId("taskSelect").disabled = true;
  byId("operatorName").disabled = true;
  byId("taskBrief").textContent = JSON.stringify(task, null, 2);
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
  if (!answer) return toast("Paste the complete manual answer before finishing.", true);
  const duration = elapsedSeconds();
  clearInterval(timerHandle);
  renderTimer();
  const finishedAt = new Date();
  const record = {
    schema_version: "safehire-termix-manual-v2",
    evidence_mode: "human_timed_manual_run",
    task_id: task.task_id,
    task_snapshot: task,
    operator: byId("operatorName").value.trim(),
    started_at: startedAt.toISOString(),
    finished_at: finishedAt.toISOString(),
    duration_seconds: Number(duration.toFixed(3)),
    cost: { amount: Number(byId("manualCost").value || 0), currency: byId("manualCurrency").value.trim() || "USD" },
    output: answer,
    attestations: {
      no_safehire_agent_called: true,
      no_pause_available_in_timer: true,
      complete_output_preserved: true,
    },
  };
  byId("finishManual").disabled = true;
  byId("manualOutput").disabled = true;
  byId("timerState").textContent = "RECORDED";
  downloadJson(`${task.task_id}-manual-output.json`, record);
  toast("Manual record downloaded. Keep it with the matching Agent output.");
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

function buildPacket() {
  const taskId = String(agentRaw.task_id || manualRaw.task_id || task?.task_id || "comparison");
  const agentIsA = crypto.getRandomValues(new Uint8Array(1))[0] % 2 === 0;
  const packetId = crypto.randomUUID();
  const outputs = agentIsA ? { A: agentRaw, B: manualRaw } : { A: manualRaw, B: agentRaw };
  const blindPacket = { schema_version: "safehire-termix-blind-packet-v2", packet_id: packetId, task_id: taskId, outputs };
  const secretKey = {
    schema_version: "safehire-termix-blind-key-v2",
    packet_id: packetId,
    task_id: taskId,
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
renderScores();
loadTask().catch((error) => toast(error.message, true));
