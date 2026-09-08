'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = 'safehire-workspace-v1';
let credential = null, current = null, services = [], busy = false, actionBusy = false, selectedCategory='grid_trading';
try { credential = JSON.parse(localStorage.getItem(key)); } catch (_) {}
function message(text) { $('message').textContent = text; }
async function api(path, body, authenticated = false) {
  const response = await fetch('/api/workspace'+path, {method: body === undefined ? 'GET' : 'POST',
    headers:{'Content-Type':'application/json', ...(authenticated ? {Authorization:'Bearer '+credential.token} : {})},
    ...(body === undefined ? {} : {body:JSON.stringify(body)})});
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'The request did not pass validation. Check your inputs.');
  return result;
}
function download(name, value) { const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
const scopes = {
  grid_trading:'Calculation or planning only. Order management, stop losses and profitability have not been verified by this marketplace.',
  rebalancing:'Read a real LP position and inspect its range. Portfolio allocation analysis is not an automatic LP rebalance. Range monitoring is available below.',
  yield_optimisation:'Compare observed rates with assumed costs. Review net gain, exit delay and capacity in the task studio. Missing data does not establish an executable migration.',
  health_factor_monitoring:'One-time account analysis and ongoing monitoring are separate services. Start 24-hour read-only monitoring below and review alerts in your inbox.'
};
function showServices(category) {
  selectedCategory=category;
  const selectedForm = {grid_trading:'grid', rebalancing:'lp', yield_optimisation:'yield', health_factor_monitoring:'health'}[category];
  for (const kind of ['grid','lp','yield','health']) $(kind+'Form').hidden = kind !== selectedForm;
  $('scope').textContent=scopes[category];
  document.querySelectorAll('[data-category]').forEach(b=>(b.classList.toggle('selected',b.dataset.category===category),b.setAttribute('aria-pressed',String(b.dataset.category===category))));
  $('services').innerHTML=services.filter(s=>s.category===category).map(s=>{
    const canQuote=!!s.availability?.can_request_quote&&!s.pause;
    const states={quote_verified:'Quote verified',unavailable:'Unavailable',paused:'Paused',stale:'Recheck needed',unchecked:'Not checked'};
    const state=states[s.availability?.state]||'Not checked';
    const knownPrice=[269224,269226,269228].includes(s.token_id);
    const scope={calculation_only:'One-time calculation',analysis_only:'Analysis only'}[s.scope]||s.scope;
    return `<article class="service-card ${canQuote?'available':''}"><div class="service-top"><span class="operator"><span class="operator-mark" aria-hidden="true">${esc(s.operator.slice(0,2).toUpperCase())}</span>${esc(s.operator)}</span><span class="badge ${canQuote?'':'unavailable'}">${esc(state)}</span></div><h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><div class="service-price"><div><small>${s.availability?.price_display?'Sample quote':'Reference fee'}</small><strong>${esc(s.availability?.price_display||(knownPrice?'0.50 U':'Request quote'))}</strong></div><div><small>Service scope</small><strong class="scope-value">${esc(scope)}</strong></div></div><p class="service-proof">${s.submitted_evidence.length?'Submitted result #'+esc(s.submitted_evidence.join(', #'))+' · Final settlement separate':'No verified delivery sample yet'}</p><details><summary>Availability &amp; evidence details</summary><p>${s.availability?.checked_at?'Checked '+esc(new Date(s.availability.checked_at*1000).toLocaleString('en-US'))+'. ':''}Actual inputs require a fresh signed quote. Network fees are separate. Delivery estimates are not refund deadlines.</p>${s.availability?.failure?`<p>${esc(s.availability.failure.reason)}</p>`:''}${s.pause?`<p>${esc(s.pause)}</p>`:''}<p>Completion rate: insufficient evidence. A submitted result is not proof of settlement, profit or independent quality.</p></details>${canQuote?`<a class="action" href="${esc(s.hire_url)}">Review quote &amp; hire <span aria-hidden="true">↗</span></a>`:'<p class="unavailable-action">Purchasing currently unavailable</p>'}</article>`;
  }).join('')+`<div class="task-studio-link"><div><h3>Need to check your inputs first?</h3><p>Review observed data, cost assumptions and acceptance criteria.</p></div><a href="/arena">Open task studio ↗</a></div>`;
}
function actionForm(w) {
  if (w.kind==='order') return '';
  const fields = w.kind==='lp'?'<label>Target range half-width / ticks<input name="half_width_ticks" type="number" min="1" max="100000" value="600" required></label><label>Slippage allowance / basis points (100 = 1%)<input name="slippage_bps" type="number" min="0" max="500" value="50" required></label><label class="check"><input type="checkbox" name="simulate_lp_exit">Simulate withdrawal and collection at the node without sending a transaction.</label>':w.kind==='health'?'<label>Assumed collateral price drop / %<input name="collateral_drop_pct" type="number" min="0" max="90" value="20" required></label><label>Assumed debt price increase / %<input name="debt_rise_pct" type="number" min="0" max="200" value="10" required></label><label>Repayment asset<select name="venue"><option value="venus-core-usdt">Venus USDT</option><option value="venus-core-usdc">Venus USDC</option></select></label><label>Repayment token amount (optional for stress analysis)<input name="amount" inputmode="decimal" placeholder="Token units, not a dollar estimate"></label>':w.kind==='grid'?'<label>Planned levels<input name="levels" type="number" min="2" max="50" value="10" required></label><label>Hypothetical budget / USD<input name="capital" type="number" min="0.01" max="1000000" step="any" value="1000" required></label><label>Assumed network cost per order / USD<input name="gas_per_order" type="number" min="0" max="1000" value="0.2" step="any" required></label><label>Assumed slippage per side / basis points<input name="slippage_bps" type="number" min="0" max="500" value="50" required></label>':'<p>Refresh rates, available cash, deposit capacity and pause status for both Venus markets, using the task budget, duration and cost assumptions.</p>';
  return `<details><summary>Prepare your next step</summary><form data-action-form="${w.id}">${fields}<label class="check"><input name="consent" type="checkbox" required>I agree to read public data and save an action preparation. No trades will be made for me.</label><button>Read data & prepare</button><p>Results include conditions, blockers and unsigned drafts where applicable. There is no broadcast control for these drafts. A successful simulation is not execution.</p></form></details>`;
}
function actionResult(w) {
  const plan=w.events.find(e=>e.kind==='action_plan')?.data;
  if (!plan) return '';
  const old=Date.now()/1000>plan.valid_until;
  const n=v=>v===null||v===undefined?'—':Number(v).toLocaleString('en-US',{maximumFractionDigits:5});
  let facts='';
  if (plan.kind==='health') facts=`<p>Current health factor: ${n(plan.metrics.current_health_factor)}; after assumed shock: ${n(plan.metrics.stressed_health_factor)}; external repayment needed under stress: ${n(plan.metrics.required_external_repay_usd)} USD.</p>`;
  if (plan.kind==='lp') facts=`<p>Target tick range: ${esc(plan.metrics.target_lower_tick)} ～ ${esc(plan.metrics.target_upper_tick)}. Theoretical inventory change for the same liquidity: token 0: ${n(plan.metrics.inventory_delta.token0)}; token 1: ${n(plan.metrics.inventory_delta.token1)}. This is not a new-position quote.</p>`;
  if (plan.kind==='grid') facts=`<p>Assumed budget per level: ${n(plan.metrics.capital_per_level_usd)} USD; modeled net value of one adjacent buy/sell cycle: ${n(plan.metrics.net_adjacent_cycle_usd)} USD. No actual fills or cumulative return are implied.</p>`;
  if (plan.kind==='yield') facts='<div class="result-table"><table><thead><tr><th>Market</th><th>Available cash / tokens</th><th>Deposit capacity / tokens</th><th>Deposits / withdrawals paused</th></tr></thead><tbody>'+plan.capacity.markets.map(r=>`<tr><td>${esc(r.venue_id)}</td><td>${n(r.cash_token_units)}</td><td>${n(r.supply_room_token_units)}</td><td>${r.mint_paused?'Yes':'No'} / ${r.redeem_paused?'Yes':'No'}</td></tr>`).join('')+'</tbody></table></div><p>Protocol cash is not your withdrawable balance. Check collateral restrictions and swap costs separately.</p>';
  return `<section class="action-result"><h4>${esc(plan.summary)}</h4><p>${old?'This preparation has expired. Refresh data before acting.':'Recent observation; no transaction authority granted'} · ${esc(new Date(plan.prepared_at).toLocaleString('en-US'))}</p>${facts}<ol>${plan.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol><p>Outstanding conditions: ${plan.blockers.length}.${plan.simulation?.passed?'Read-only node simulation passed. No transaction sent.':''}</p><ul>${plan.blockers.map(b=>`<li>${esc(b)}</li>`).join('')}</ul><button data-plan-export="${w.id}">Download full preparation</button><details><summary>Conditions & source data</summary><pre>${esc(JSON.stringify(plan,null,2))}</pre></details></section>`;
}

function deliveryTable(delivery) {
  if (!delivery) return '';
  if (!delivery.acceptance && delivery.verification?.content) return `<details open><summary>Provider output (content review pending)</summary><p>A matching file hash does not prove the conclusion is correct. Check inputs, calculations and usefulness. Do not automatically transfer funds.</p><pre>${esc(delivery.verification.content)}</pre></details>`;
  if (!delivery.acceptance?.passed) return '';
  try {
    const result=JSON.parse(delivery.verification.content);
    if (!Array.isArray(result.buys)||!Array.isArray(result.sells)) return '';
    return `<details open><summary>View checked grid calculation</summary><p>Input reference price: ${esc(result.mark)}; hypothetical budget: ${esc(result.budgetUsd)} USD. This is a calculation table, not placed orders. The reference is not a current market price.</p><div class="result-table"><table><thead><tr><th>Side</th><th>Price</th><th>USD per level</th><th>Quantity</th></tr></thead><tbody>${[...result.buys,...result.sells].map(row=>`<tr><td>${row.side==='buy'?'BUY':'SELL'}</td><td>${esc(row.price)}</td><td>${esc(row.sizeUsd)}</td><td>${esc(row.amount)}</td></tr>`).join('')}</tbody></table></div><p>Record whether this result helped with your task below. Correct arithmetic does not establish value for money or guaranteed returns.</p></details>`;
  } catch (_) { return ''; }
}
function display() {
  $('notificationPanel').hidden=!credential; $('forms').hidden=!credential; $('create').hidden=!!credential; $('backup').hidden=!credential; $('export').hidden=!credential; $('switchSpace').hidden=!credential;
  $('workspaceState').textContent=credential?'Private workspace connected. Save your recovery file and keep it out of public submission materials.':'No private workspace connected yet.';
}
async function refresh() {
  if (!credential || busy || actionBusy || ($('watches').contains(document.activeElement) && document.activeElement.matches('input,textarea,select'))) return;
  busy=true;
  try {
    current=await api('/spaces/'+credential.space_id,undefined,true);
    $('watches').innerHTML=current.watches.map(w=>{
      const unread=w.events.filter(e=>['alert','delivery_ready'].includes(e.kind)&&!e.read_at).length;
      const latest=w.latest; const obs=latest.observation;
      const lastObservation=w.events.find(e=>e.kind==='observation'||e.kind==='alert'||e.kind==='delivery_ready');
      const stale=!!w.active && Date.now()/1000-(lastObservation?.at||w.created)>600;
      const priorDelivery=w.events.find(e=>e.data?.delivery);
      const delivery=latest.delivery||priorDelivery?.data.delivery;
      const historicDelivery=!latest.delivery&&!!delivery;
      const quality=delivery?.acceptance;
      const detail=obs ? (w.kind==='yield'?`Higher modeled net yield: ${latest.comparison.best_under_assumptions}; exit conditions and capacity remain unknown`:w.kind==='grid'?`Pool price: ${Number(obs.price_usdt_per_wbnb).toFixed(4)} USDT/WBNB；${latest.in_range?'Within range':'Outside range'}`:w.kind==='health'?`Health factor: ${obs.health_factor??'No debt'}; repayment to target: ${latest.repay_to_target_usd} USD`:`Current tick ${obs.current_tick}; range ${obs.lower_tick}～${obs.upper_tick}；${latest.in_range?'In range':'Out of range'}`) : latest.chain ? `Order ${latest.chain.job_id} · ${latest.chain.budget_u} U · ${latest.chain.status}` : latest.error||'Waiting for the first server observation';
      return `<article class="watch ${esc(w.state)}"><span class="badge">${stale?'Stale data; check the service':esc(w.state)}${!w.active?' · Monitoring stopped':''}</span><h3>${esc(w.kind==='order'?'Order #'+w.spec.job_id:w.kind==='health'?'Lending account check':w.kind==='grid'?'Grid range monitor':w.kind==='yield'?'Ongoing yield comparison':'LP position #'+w.spec.position_id)}</h3><p>${esc(detail)}</p>${historicDelivery?`<p>Historical delivery (${esc(new Date(priorDelivery.at*1000).toLocaleString('en-US'))}). The latest read failed or has not reverified this result. This is not the current chain state.</p>`:''}${deliveryTable(delivery)}${actionResult(w)}${actionForm(w)}${quality?`<p>Calculation review: ${quality.passed?'Passed':'Failed: '+esc(quality.failures.join('; '))}. Human quality review is pending.</p>`:''}<p>${unread?'You have '+unread+' unread alerts':'No unread alerts'} · Last checked ${esc(lastObservation?new Date(lastObservation.at*1000).toLocaleString('en-US'):'Not observed yet')} · Monitoring expires ${esc(new Date(w.expires*1000).toLocaleString('en-US'))}</p>${w.kind==='order'?`<a class="action" href="/hire-live?job_id=${w.spec.job_id}">Open order, review or refund</a>`:'<a class="action" href="/arena">Explore next steps</a>'} <button data-ack="${w.id}">Mark as read</button> ${w.active?`<button data-pause="${w.id}">Pause monitoring</button>`:`<button data-resume="${w.id}">Resume monitoring</button>`}<details><summary>Review this result</summary><form data-feedback-form="${w.id}"><label>Was this useful for your task?<select name="useful"><option value="not_reviewed">Not reviewed</option><option value="yes">Useful</option><option value="partly">Partly useful</option><option value="no">Not useful</option></select></label><label>Describe the benefit or problem<textarea name="comment" maxlength="1500" required></textarea></label><label>Would you buy this service again at the same price?<select name="repurchase"><option value="unknown">Undecided / not purchased</option><option value="yes">Yes, I would</option><option value="no">No, I would not</option></select></label><label class="check"><input name="used_ai" type="checkbox">AI helped write this feedback</label><button>Save my feedback</button><p class="muted">This is workspace-user feedback without independent identity verification. It does not count as an independent blind review.</p></form></details><details><summary>Raw observations & timestamps (latest 300)</summary><pre>${esc(JSON.stringify(w.events,null,2))}</pre></details></article>`;
    }).join('')||'<p>No tasks yet. Add a public order or a monitoring target.</p>';
  } catch(e){message(e.message);} finally{busy=false;}
}
$('create').onclick=async()=>{try{credential=await api('/spaces',{});localStorage.setItem(key,JSON.stringify(credential));display();await refresh();await refreshNotifications();}catch(e){message(e.message);}};
$('backup').onclick=()=>download('safehire-private-recovery.json',credential);
$('restore').onchange=async e=>{try{const file=e.target.files[0];if(!file||file.size>4096)throw new Error('Choose a recovery file smaller than 4 KB.');const value=JSON.parse(await file.text());if(!/^[a-f0-9]{32}$/.test(value.space_id)||typeof value.token!=='string'||value.token.length<32||value.token.length>128)throw new Error('Invalid recovery credential');credential=value;await api('/spaces/'+value.space_id,undefined,true);localStorage.setItem(key,JSON.stringify(value));display();await refresh();await refreshNotifications();}catch(err){credential=null;display();message(err.message);}};
$('export').onclick=()=>current&&download('safehire-service-records.json',current);
$('refresh').onclick=refresh;
for(const kind of ['order','health','lp','grid','yield']) $(kind+'Form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target), body={kind,consent:f.has('consent')};if(kind==='order'){body.job_id=Number(f.get('job_id'));body.notify_provider=f.has('notify_provider');}if(kind==='health'){body.account=f.get('account');body.threshold=Number(f.get('threshold'));body.target=Number(f.get('target'));}if(kind==='lp')body.position_id=Number(f.get('position_id'));if(kind==='grid'){body.lower=Number(f.get('lower'));body.upper=Number(f.get('upper'));}if(kind==='yield'){for(const n of ['capital','days','cost','minimum_gain'])body[n]=Number(f.get(n));body.current_venue=f.get('current_venue');}try{await api('/spaces/'+credential.space_id+'/watches',body,true);await refresh();message('Saved. The server will keep checking. Review or pause it here.');}catch(err){message(err.message);}};
$('watches').onclick=async e=>{const b=e.target.closest('button');if(!b || (!b.dataset.pause && !b.dataset.ack && !b.dataset.resume && !b.dataset.planExport))return;try{if(b.dataset.planExport){const w=current.watches.find(w=>w.id===b.dataset.planExport);return download('safehire-action-preparation.json',w.events.find(e=>e.kind==='action_plan').data);}if(b.dataset.resume)await api(`/spaces/${credential.space_id}/watches/${b.dataset.resume}/resume`,{},true);if(b.dataset.pause)await api(`/spaces/${credential.space_id}/watches/${b.dataset.pause}/pause`,{},true);if(b.dataset.ack)await api(`/spaces/${credential.space_id}/watches/${b.dataset.ack}/acknowledge`,{},true);await refresh();}catch(err){message(err.message);}};
$('compareForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);const body={consent:f.has('consent')};for(const n of ['price','budgetUsd','levels','spanPct'])body[n]=Number(f.get(n));const button=e.target.querySelector('button');button.disabled=true;try{const r=await api('/compare-grid',body);$('comparison').innerHTML=r.offers.map(o=>`<p><strong>${esc(o.name)}</strong>：${o.quote?esc(o.quote.quote.price_display)+'; estimated '+esc(o.quote.quote.estimated_completion_seconds)+' seconds. Signature verified; not purchased.':esc(o.error||o.reason)}</p>`).join('');}catch(err){message(err.message);}finally{button.disabled=false;}};
document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>showServices(b.dataset.category));
(async()=>{display();try{const [cap,list]=await Promise.all([api('/capabilities'),api('/services')]);$('runtime').textContent=cap.server_followup?'Server monitoring active · Checks about every 5 minutes · No automatic transactions':cap.enabled?'Monitoring is currently unavailable. Refresh later and do not rely on it yet.':'Server follow-up is not enabled on this deployment. Purchasing and public evidence remain accessible.';services=list.services;showServices('grid_trading');await refresh();await refreshNotifications();}catch(e){message(e.message);}setInterval(refresh,30000);})();

$('watches').addEventListener('submit', async e => {
  const form = e.target.closest('[data-feedback-form]'); if (!form) return; e.preventDefault();
  const f = new FormData(form);
  try { await api(`/spaces/${credential.space_id}/watches/${form.dataset.feedbackForm}/feedback`,
    {useful:f.get('useful'), comment:f.get('comment'), used_ai:f.has('used_ai'), repurchase:f.get('repurchase')},true);
    message('Feedback saved as your own statement, not an independent review or wallet identity check.'); await refresh();
  } catch (error) { message(error.message); }
});

$('watches').addEventListener('submit', async e=>{
  const form=e.target.closest('[data-action-form]');if(!form)return;e.preventDefault();
  const f=new FormData(form),body={consent:f.has('consent')};
  for(const name of ['collateral_drop_pct','debt_rise_pct','half_width_ticks','slippage_bps','levels','capital','gas_per_order'])if(f.has(name))body[name]=Number(f.get(name));
  if(f.has('simulate_lp_exit'))body.simulate_lp_exit=true;
  if(f.get('amount')?.trim()){body.amount=f.get('amount').trim();body.venue=f.get('venue');}
  const button=form.querySelector('button');button.disabled=true;actionBusy=true;message('Reading observed data and checking conditions. This may take tens of seconds. No transaction will be sent.');
  try{await api(`/spaces/${credential.space_id}/watches/${form.dataset.actionForm}/action-plan`,body,true);actionBusy=false;button.disabled=false;button.focus();await refresh();message('Preparation saved. Review the results and outstanding conditions.');}catch(error){message(error.message);}finally{actionBusy=false;if(button.isConnected)button.disabled=false;}
});
setInterval(async()=>{try{services=(await api('/services')).services;showServices(selectedCategory);}catch(_){services=services.map(s=>({...s,availability:{state:'stale',can_request_quote:false}}));showServices(selectedCategory);}},60000);

$('switchSpace').onclick=()=>{credential=null;current=null;localStorage.removeItem(key);$('watches').innerHTML='';display();message('This browser has disconnected. Server records remain; reconnect using your recovery file.');};

async function refreshNotifications(){
  if(!credential)return;
  try{const n=await api(`/spaces/${credential.space_id}/notifications`,undefined,true);
    $('notificationState').textContent=n.enabled?'Phone alerts enabled. Delivery acceptance and human reading are reported separately below.':n.bound?'Device bound. Enter the verification code from your phone.':'Phone alerts are not connected.';
    $('pushVerifyForm').hidden=!n.bound||n.verified; $('pushUnsubscribe').hidden=!n.bound;
    const labels={pending:'Waiting to send or retry',sending:'Sending',accepted_by_provider:'Accepted by Bark; human reading unverified',failed:'Failed; retries stopped',expired:'Delivery window expired',cancelled:'Cancelled'};
    $('notificationLog').innerHTML=n.deliveries.map(r=>`<p>Alert ${r.id}：${esc(labels[r.state]||r.state)} · Attempts: ${r.attempts}</p>`).join('')||'<p>No push notification records yet.</p>';
  }catch(e){$('notificationState').textContent=e.message;}
}
$('pushBindForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),b=e.target.querySelector('button');b.disabled=true;try{const r=await api(`/spaces/${credential.space_id}/notifications/bind`,{device_key:f.get('device_key').trim(),consent:f.has('consent')},true);e.target.reset();message(r.provider_accepted?'Verification sent to Bark. Check your phone and enter the code.':'Bark did not accept the verification. Check the device key and retry.');await refreshNotifications();}catch(err){message(err.message);}finally{b.disabled=false;}};
$('pushVerifyForm').onsubmit=async e=>{e.preventDefault();try{await api(`/spaces/${credential.space_id}/notifications/verify`,{code:new FormData(e.target).get('code')},true);e.target.reset();await refreshNotifications();message('Phone receipt verified. New alerts are now enabled.');}catch(err){message(err.message);}};
$('pushUnsubscribe').onclick=async()=>{try{await api(`/spaces/${credential.space_id}/notifications/unsubscribe`,{},true);await refreshNotifications();message('Alerts disabled and the server device credential removed.');}catch(err){message(err.message);}};
setInterval(refreshNotifications,30000);
