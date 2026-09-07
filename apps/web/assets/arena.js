'use strict';
(() => {
// Keep large JSON integers as exact numeric tokens, distinct from decimal strings.
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

  const responseBytes = new WeakMap();
  const $ = id => document.getElementById(id);
  const categories = {
    rebalancing: ['LP ranges', 'Tick alignment, range inventory, churn and cost caps. Not portfolio weighting.'],
    grid_trading: ['Grid trading', 'One adjacent cycle after both-side fees, tax, slippage and gas; not a backtest.'],
    yield_optimisation: ['Yield routing', 'Compare net horizon income with staying in the current venue; check capacity and exit delay.'],
    health_factor_monitoring: ['Lending protection', 'Asset-level collateral drops and debt-price increases; quantify repay and budget shortfall.']
  };
  let category = 'rebalancing', task = null, reference = null, capabilities = null;
  let saved = [], selected = new Set(), busy = false, pendingSubmission = null;
  let acceptedDelivery = null;
  let walletObservation = null;
  const sessionKey = 'safehire-arena-session-v1';
  const requestKey = () => crypto.randomUUID ? crypto.randomUUID() : Array.from(crypto.getRandomValues(new Uint8Array(16)), b => b.toString(16).padStart(2, '0')).join('');
  const json = value => taskJSON.stringify(value, null, 2);
  function status(text) { $('status').textContent = text; }
  function element(tag, text, className) {
    const item = document.createElement(tag);
    if (text !== undefined) item.textContent = text;
    if (className) item.className = className;
    return item;
  }
  async function api(path, options = {}) {
    const headers = { ...(options.body ? {'Content-Type': 'application/json'} : {}), ...(options.headers || {}) };
    if (task) headers.Authorization = `Bearer ${task.task_token}`;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 70000);
    try {
      const response = await fetch(`/api/arena${path}`, { ...options, headers, cache: 'no-store', signal: controller.signal });
      const raw = await response.text();
      const result = taskJSON.parse(raw);
      if (result && typeof result === 'object') responseBytes.set(result, raw);
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : json(result.detail || result));
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The request timed out. Refresh task status before retrying a save. No payment was sent.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function rememberTask() {
    try {
      if (task) sessionStorage.setItem(sessionKey, json({task, category}));
      else sessionStorage.removeItem(sessionKey);
    } catch (_) { $('task-meta').textContent += ' · Browser recovery unavailable; keep this tab open.'; }
  }
  function taskDraft() {
    for (const input of $('task-form').querySelectorAll('input')) {
      if (!input.reportValidity()) throw new Error('Complete the task form before continuing.');
    }
    return $('task-input').value;
  }
  function renderTaskForm() {
    const host = $('task-form'); host.replaceChildren();
    let draft;
    try { draft = taskJSON.parse($('task-input').value); } catch (_) { return; }
    const labels = {
      capital_usd: 'Amount to analyse (USD)', max_cost_usd: 'Maximum total cost (USD)',
      max_slippage_bps: 'Maximum price slippage (basis points; 100 = 1%)',
      max_snapshot_age_seconds: 'Maximum data age (seconds)',
      current_tick: 'Current pool price tick', old_lower_tick: 'Existing range: lower tick',
      old_upper_tick: 'Existing range: upper tick', tick_spacing: 'Pool tick spacing',
      half_width_ticks: 'New range: half width in ticks', liquidity_raw: 'Position liquidity (raw units)',
      token0_decimals: 'First token decimal places', token1_decimals: 'Second token decimal places',
      estimated_cost_usd: 'Estimated transaction cost (USD)', slippage_bps: 'Estimated slippage (100 = 1%)',
      current_price: 'Current price', lower_price: 'Lowest grid price', upper_price: 'Highest grid price',
      levels: 'Number of grid levels', fee_bps_per_side: 'Fee per side (100 = 1%)',
      transfer_tax_bps_per_side: 'Token transfer tax per side (100 = 1%)',
      slippage_bps_per_side: 'Slippage per side (100 = 1%)', gas_usd_per_order: 'Network cost per order (USD)',
      stop_price: 'Stop price', current_apy_pct: 'Current annual compounded yield (%)',
      horizon_days: 'Planned holding period (days)', min_improvement_usd: 'Minimum extra income required (USD)',
      venue_id: 'Market identifier', apy_pct: 'Annual compounded yield (%)',
      migration_cost_usd: 'Cost to move funds (USD)', capacity_usd: 'Available capacity (USD)',
      withdrawal_delay_days: 'Withdrawal delay (days)', asset: 'Asset name', value_usd: 'Position value (USD)',
      liquidation_threshold: 'Liquidation threshold (0 to 1)', price_drop_pct: 'Assumed price drop (%)',
      price_rise_pct: 'Assumed debt price rise (%)', target_health_factor: 'Target lending safety ratio',
      available_repay_usd: 'Available repayment budget (USD)'
    };
    function fields(value, parent, path) {
      for (const [key, val] of Object.entries(value)) {
        const next = [...path, key];
        if (val !== null && typeof val === 'object' && !JSON.isRawJSON?.(val)) {
          const group = element('fieldset'); group.append(element('legend', /^\d+$/.test(key) ? `Item ${Number(key) + 1}` : key.replaceAll('_', ' ')));
          fields(val, group, next); parent.append(group); continue;
        }
        const label = element('label', labels[key] || key.replaceAll('_', ' '));
        const input = document.createElement('input'); input.value = JSON.isRawJSON?.(val) ? val.rawJSON : String(val);
        input.type = typeof val === 'number' ? 'number' : 'text';
        input.required = true;
        if (input.type === 'number') input.step = 'any';
        input.addEventListener('input', () => {
          input.setCustomValidity('');
          if (input.value.trim() === '' || !input.checkValidity()) { input.setCustomValidity('Enter a valid value.'); return; }
          input.setCustomValidity('');
          if (key === 'liquidity_raw' && (!/^[1-9][0-9]*$/.test(input.value) || input.value.length > 39 || BigInt(input.value) > (2n ** 128n - 1n))) {
            input.setCustomValidity('Enter an exact positive liquidity integer.'); return;
          }
          const current = taskJSON.parse($('task-input').value);
          let target = current; for (const part of next.slice(0, -1)) target = target[part];
          target[next[next.length - 1]] = JSON.isRawJSON?.(val) ? JSON.rawJSON(input.value) : (typeof val === 'number' ? Number(input.value) : input.value);
          $('task-input').value = json(current);
          reference = null; $('copy-reference').disabled = true; $('reference').replaceChildren();
          status(task ? 'Draft changed. The saved task remains frozen; create a new task to use these changes.' : 'Draft updated. Source data and assumptions still need review.');
        });
        label.append(input); parent.append(label);
      }
    }
    fields(draft.inputs, host, ['inputs']);
    const limits = element('fieldset'); limits.append(element('legend', 'Your limits'));
    fields(draft.limits, limits, ['limits']); host.append(limits);
  }

  async function act(fn) {
    if (busy) return;
    busy = true;
    try { await fn(); } catch (error) { status(`Not completed: ${error.message}`); }
    finally { busy = false; }
  }
  function renderReport(report, parent) {
    const card = element('article', undefined, 'report-card');
    card.append(element('h3', `${report.agent_ref} · ${report.policy_accepted ? 'CONSTRAINTS PASS' : 'BLOCKED'}`));
    card.append(element('p', 'Caller-supplied model validation · no execution or verified authorship', 'muted'));
    const list = element('ul');
    for (const c of report.checks) {
      list.append(element('li', `${c.passed ? 'PASS' : 'FAIL'}  ${c.name}${c.detail ? ` — ${c.detail}` : ''}`, c.passed ? 'pass' : 'fail'));
    }
    card.append(list);
    const details = element('details');
    details.append(element('summary', 'Recomputed metrics'), element('pre', json(report.metrics)));
    card.append(details); parent.append(card);
  }
  function categoryButtons() {
    $('categories').replaceChildren();
    for (const [key, [label]] of Object.entries(categories)) {
      const button = element('button', label);
      button.setAttribute('aria-pressed', String(key === category));
      button.addEventListener('click', () => act(async () => {
        if (task && !confirm('Switching clears this tab’s task access token. Export your private bundle first. Continue?')) return;
        category = key; task = null; saved = []; reference = null; selected.clear();
        $('walkthrough-result').replaceChildren();
        renderSaved(); await loadExample(); categoryButtons();
      }));
      $('categories').append(button);
    }
    $('task-title').textContent = categories[category][0];
    $('category-detail').textContent = categories[category][1];
  }
  async function loadExample() {
    $('venus-result').textContent = '';
    reference = null; pendingSubmission = null; $('copy-reference').disabled = true;
    $('proposal-input').value = ''; $('proposal-result').replaceChildren(); $('comparison-result').replaceChildren();
    acceptedDelivery = null; $('export-delivery').disabled = true; $('delivery-result').textContent = '';
    const data = await api('/examples');
    $('task-input').value = json(data.tasks[category]);
    renderTaskForm();
    $('reference').replaceChildren();
    status('SYNTHETIC EXAMPLE loaded. The block and asset values are not chain observations.');
  }
  function renderSaved() {
    $('saved-proposals').replaceChildren();
    for (const p of saved) {
      const label = element('label', undefined, 'saved-row');
      const box = document.createElement('input'); box.type = 'checkbox'; box.checked = selected.has(p.proposal_id);
      box.addEventListener('change', () => {
        if (box.checked) selected.add(p.proposal_id); else selected.delete(p.proposal_id);
        $('compare').disabled = selected.size < 2 || selected.size > 3;
      });
      const report = taskJSON.parse(p.report_json);
      const name = element('span', `${report.agent_ref} · ${report.policy_accepted ? 'passed at evaluation time' : 'blocked at evaluation time'}`);
      name.append(element('small', `Exact output SHA-256 ${p.raw_sha256}`));
      label.append(box, name); $('saved-proposals').append(label);
    }
    $('verify-delivery').disabled = !task;
    $('submit').disabled = !task; $('export').disabled = !task; $('refresh-task').disabled = !task;
    $('create').disabled = Boolean(capabilities && !capabilities.task_storage_enabled);
    $('compare').disabled = selected.size < 2 || selected.size > 3;
    $('task-meta').textContent = task ? `Task ${task.task_id} · version ${task.version}` : 'No task opened.';
    renderProviders(); rememberTask();
  }
  function renderProviders() {
    if (!capabilities) return;
    $('providers').replaceChildren(); $('provider-select').replaceChildren();
    const rows = capabilities.providers.providers.filter(p => p.category === category);
    for (const p of rows) {
      $('providers').append(element('div', `${p.operator_label} · ${p.agent_ref} · ${p.reviewed_scope} · ${p.quote_enabled ? 'quote configured' : 'quote disabled'}`, 'provider-row'));
      const option = element('option', `${p.operator_label} — ${p.skill_id}`); option.value = p.agent_ref;
      $('provider-select').append(option);
    }
    $('open-hire').disabled = !task || !rows.length;
    $('quote').disabled = !task || !capabilities.quotes_enabled || !rows.some(p => p.quote_enabled);
  }
  $('task-input').addEventListener('change', renderTaskForm);
  $('forget-task').addEventListener('click', () => act(async () => {
    if (!confirm('Remove this tab’s access to the private task? Export first. The server record is not deleted.')) return;
    task = null; saved = []; selected.clear(); pendingSubmission = null; renderSaved();
    status('Task access removed from this tab.');
  }));
  $('walkthrough').addEventListener('click', () => act(async () => {
    const data = await api(`/synthetic-walkthrough/${category}`);
    $('walkthrough-result').replaceChildren(); $('scenario-story').textContent = data.narrative;
    for (const report of data.comparison.reports) renderReport(report, $('walkthrough-result'));
    status('Synthetic local plans compared. Zero real providers, no payment and no reputation changes.');
  }));
  $('wallet-read').addEventListener('click', () => act(async () => {
    walletObservation = null; $('wallet-export').disabled = true;
    $('wallet-summary').replaceChildren(); $('wallet-result').textContent = '';
    if (!$('wallet-consent').checked) throw new Error('Approve the public account read first.');
    const data = await api('/sources/wallet', {method: 'POST', body: json({
      account: $('wallet-account').value.trim(), consent_read_public_account: true
    })});
    walletObservation = data;
    const display = (value, digits = 2) => value === null ? 'unknown' : Number(value).toLocaleString('en-US', {maximumFractionDigits: digits});
    for (const row of data.assets) {
      $('wallet-summary').append(element('p', `${row.symbol}: ${row.balance ?? 'unavailable'} · reference USD ${display(row.reference_value_usd)} · priced-subset share ${display(row.share_of_priced_subset_pct)}%`));
    }
    $('wallet-summary').append(element('p', `Priced subset only: USD ${display(data.summary.priced_subset_value_usd)}. Other tokens and chains are not covered. ${data.summary.concentration_warning ? 'One asset is at least 80% of this priced subset; this is not a sell recommendation.' : ''}`));
    $('wallet-result').textContent = json(data); $('wallet-export').disabled = false;
    status('Wallet observation complete. Review missing values and coverage; no trade or yield inferred.');
  }));
  $('wallet-export').addEventListener('click', () => {
    if (!walletObservation) return;
    const url = URL.createObjectURL(new Blob([responseBytes.get(walletObservation)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `safehire-wallet-${walletObservation.block_number}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  $('sample').addEventListener('click', () => act(loadExample));
  $('preview').addEventListener('click', () => act(async () => {
    const data = await api('/preview', {method: 'POST', body: taskDraft()});
    reference = data.reference_proposal; $('reference').replaceChildren();
    renderReport(data.report, $('reference')); $('copy-reference').disabled = false;
    $('proposal-input').value = json(reference);
    status('Reference plan recomputed locally. This is not a hired provider’s delivery.');
  }));
  $('create').addEventListener('click', () => act(async () => {
    if (task && !confirm('Replace this tab’s current task access token? Export first.')) return;
    task = await api('/tasks', {method: 'POST', body: taskDraft()});
    $('venus-result').textContent = '';
    acceptedDelivery = null; $('export-delivery').disabled = true; $('delivery-result').textContent = '';
    saved = []; selected.clear(); renderSaved();
    status('Private task opened. Subsequent proposals are checked against its frozen inputs, not edited textarea values.');
  }));
  $('lp-create').addEventListener('click', () => act(async () => {
    if (category !== 'rebalancing') throw new Error('Select LP range and review width, costs and slippage first.');
    if (!$('lp-consent').checked) throw new Error('Approve the public position read first.');
    const positionId = Number($('lp-position').value);
    if (!Number.isSafeInteger(positionId) || positionId <= 0) throw new Error('Enter a positive position number.');
    if (task && !confirm('Replace this tab’s task access token? Export the existing private bundle first.')) return;
    $('lp-result').textContent = '';
    const data = await api('/source-tasks/pancakeswap-lp', {method: 'POST', body: json({
      template: taskJSON.parse(taskDraft()), position_id: positionId, consent_read_public_position: true
    })});
    task = {task_id: data.task_id, task_token: data.task_token, version: data.version};
    $('task-input').value = json(data.task); renderTaskForm();
    $('lp-result').textContent = json({observation: data.source_observation, remaining_assumptions: data.remaining_assumptions});
    acceptedDelivery = null; reference = null; pendingSubmission = null;
    $('export-delivery').disabled = true; $('delivery-result').textContent = '';
    $('copy-reference').disabled = true; $('reference').replaceChildren(); $('proposal-result').replaceChildren();
    $('comparison-result').replaceChildren(); $('proposal-input').value = '';
    saved = []; selected.clear(); renderSaved();
    status('Real LP range and liquidity frozen. Width, cost and slippage remain assumptions. No trade or payment.');
  }));
  $('venus-create').addEventListener('click', () => act(async () => {
    if (!$('venus-consent').checked) throw new Error('Approve the public source read first.');
    if (category !== 'yield_optimisation') throw new Error('Select Yield routing and review its capital/cost/capacity assumptions first.');
    if (task && !confirm('Replace this tab’s task access token? Export the existing private bundle first.')) return;
    $('venus-result').textContent = '';
    const data = await api('/source-tasks/venus-yield', {method: 'POST', body: json({
      template: taskJSON.parse(taskDraft()), current_venue: $('venus-current').value,
      account: $('venus-account').value.trim() || null, consent_read_public_account: true
    })});
    task = {task_id: data.task_id, task_token: data.task_token, version: data.version};
    $('task-input').value = json(data.task); renderTaskForm();
    $('venus-result').textContent = json({observation: data.source_observation, remaining_assumptions: data.remaining_assumptions});
    acceptedDelivery = null; reference = null; pendingSubmission = null;
    $('export-delivery').disabled = true; $('delivery-result').textContent = '';
    $('copy-reference').disabled = true; $('reference').replaceChildren(); $('proposal-result').replaceChildren();
    $('comparison-result').replaceChildren(); $('proposal-input').value = '';
    saved = []; selected.clear(); renderSaved();
    status('Server-read Venus rates frozen and recorded. Capital, costs and capacity are still assumptions. No wallet signature or payment.');
  }));
  $('venus-template').addEventListener('click', () => act(async () => {
    if (task && !confirm('This clears this tab’s task access token. Export the current bundle first. Continue?')) return;
    category = 'yield_optimisation'; task = null; reference = null; saved = []; selected.clear();
    await loadExample();
    const draft = taskJSON.parse($('task-input').value);
    draft.inputs.venues[0].venue_id = 'venus-core-usdt';
    draft.inputs.venues[1].venue_id = 'venus-core-usdc';
    $('task-input').value = json(draft); renderTaskForm(); $('venus-result').textContent = '';
    categoryButtons(); renderSaved();
    status('Venus template loaded. Capital, costs, capacity and delay are illustrative assumptions: edit before creating. Rates will be replaced by server reads.');
  }));
  $('copy-reference').addEventListener('click', () => { if (reference) $('proposal-input').value = json(reference); });
  $('submit').addEventListener('click', () => act(async () => {
    if (!task) throw new Error('Open a private task first.');
    const body = json({proposal_text: $('proposal-input').value, expected_version: task.version});
    if (!pendingSubmission || pendingSubmission.body !== body || pendingSubmission.task_id !== task.task_id) {
      pendingSubmission = {body, task_id: task.task_id, key: requestKey()};
    }
    const result = await api(`/tasks/${task.task_id}/proposals`, {method: 'POST',
      headers: {'Idempotency-Key': pendingSubmission.key}, body});
    pendingSubmission = null;
    task.version = result.version; $('proposal-result').replaceChildren(); renderReport(result.report, $('proposal-result'));
    const bundle = await api(`/tasks/${task.task_id}`); task.version = bundle.version; saved = bundle.proposals; renderSaved();
    status('Exact proposal bytes saved. No provider reputation or paid-delivery count was changed.');
  }));
  $('compare').addEventListener('click', () => act(async () => {
    const data = await api(`/tasks/${task.task_id}/compare`, {method: 'POST', body: json({proposal_ids: [...selected]})});
    $('comparison-result').replaceChildren();
    for (const report of data.reports) renderReport(report, $('comparison-result'));
    status(`Fresh checks completed. ${data.eligible_agent_refs.length} proposal(s) satisfy this task. No quality winner is inferred.`);
  }));
  $('refresh-task').addEventListener('click', () => act(async () => {
    const bundle = await api(`/tasks/${task.task_id}`); task.version = bundle.version;
    saved = bundle.proposals; pendingSubmission = null; selected.clear(); renderSaved();
    status('Task version refreshed without discarding this tab’s access token.');
  }));
  $('export').addEventListener('click', () => act(async () => {
    const bundle = await api(`/tasks/${task.task_id}`);
    const url = URL.createObjectURL(new Blob([responseBytes.get(bundle)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `safehire-private-${task.task_id}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    status(`Exported. Preserve this head independently: ${bundle.integrity.head}. Bundle contains private inputs, not the task token.`);
  }));
  $('open-hire').addEventListener('click', () => act(async () => {
    if (!task) throw new Error('Open a private task first.');
    const provider = capabilities.providers.providers.find(p => p.agent_ref === $('provider-select').value);
    if (!provider || provider.category !== category) throw new Error('Select a matching provider route.');
    if (provider.reviewed_scope.includes('not_lp_execution')) throw new Error('This provider offers portfolio analysis, not LP range management. Choose a compatible LP provider before hiring for this task.');
    const bundle = await api(`/tasks/${task.task_id}`);
    sessionStorage.setItem('safehire-arena-handoff-v1', json({task: bundle.task, agent_ref: provider.agent_ref}));
    const params = new URLSearchParams({skill_id: provider.skill_id, agent_token_id: String(provider.token_id), arena: '1'});
    location.assign(`/hire-live?${params}`);
  }));
  $('quote').addEventListener('click', () => act(async () => {
    if (!$('consent').checked) throw new Error('Approve sending the task to this provider first.');
    const data = await api(`/tasks/${task.task_id}/quote`, {method: 'POST', body: json({agent_ref: $('provider-select').value, consent_send_task: true})});
    $('quote-result').textContent = json(data); status('Read-only quote returned. No payment, delivery or signature was requested.');
  }));
  $('verify-delivery').addEventListener('click', () => act(async () => {
    acceptedDelivery = null; $('export-delivery').disabled = true; $('delivery-result').textContent = '';
    if (!task) throw new Error('Open the frozen private task first.');
    const rawJob = $('delivery-job').value.trim();
    const job = Number(rawJob);
    if (!/^[1-9][0-9]*$/.test(rawJob) || !Number.isSafeInteger(job)) throw new Error('Enter a positive safe-integer job ID.');
    const data = await api(`/tasks/${task.task_id}/delivery-acceptance`, {method: 'POST',
      body: json({job_id: job, agent_ref: $('provider-select').value})});
    acceptedDelivery = data; $('delivery-result').textContent = json(data); $('export-delivery').disabled = false;
    status('Delivery checked against the frozen task. Review the acceptance and source limits; no payment was authorized.');
  }));
  $('export-delivery').addEventListener('click', () => {
    if (!acceptedDelivery) return;
    const url = URL.createObjectURL(new Blob([responseBytes.get(acceptedDelivery)], {type: 'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = `safehire-acceptance-${acceptedDelivery.job_id}.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  act(async () => {
    capabilities = await api('/capabilities');
    let recovery = null;
    try { recovery = taskJSON.parse(sessionStorage.getItem(sessionKey)); } catch (_) { /* unavailable browser storage */ }
    categoryButtons(); await loadExample();
    if (recovery && recovery.task && categories[recovery.category]) {
      task = recovery.task; category = recovery.category;
      try {
        const bundle = await api(`/tasks/${task.task_id}`);
        task.version = bundle.version; saved = bundle.proposals;
        $('task-input').value = typeof bundle.task_json === 'string' ? bundle.task_json : json(bundle.task);
        renderTaskForm(); categoryButtons();
        status('Private task restored for this tab. Checks still use the original frozen snapshot; refresh does not make old data fresh.');
      } catch (error) {
        status(`Saved task could not be read: ${error.message}. Refresh task status to retry, or forget this task.`);
      }
    }
    renderSaved();
    if (!capabilities.task_storage_enabled) status('Preview is available. Private task storage is disabled until the deployment enables SAFEHIRE_ARENA_ENABLED=true.');
  });
})();
