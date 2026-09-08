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
  if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : '请求未通过检查，请核对输入');
  return result;
}
function download(name, value) { const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})); const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
const scopes = {
  grid_trading:'购买的是计算或计划。实际订单管理、止损与盈利尚未由本市场验证。',
  rebalancing:'读取真实 LP 仓位并检查区间；组合权重分析不等于 LP 自动调仓。可以在下面开启区间监控。',
  yield_optimisation:'比较真实读取的利率和假设成本。在任务页检查净增收益、退出等待和容量；数据缺失时不能当作可执行迁移。',
  health_factor_monitoring:'一次账户检查与持续监控分别展示。下面可开启 24 小时只读监控并查看站内提醒。'
};
function showServices(category) {
  selectedCategory=category;
  const selectedForm = {grid_trading:'grid', rebalancing:'lp', yield_optimisation:'yield', health_factor_monitoring:'health'}[category];
  for (const kind of ['grid','lp','yield','health']) $(kind+'Form').hidden = kind !== selectedForm;
  $('scope').textContent=scopes[category];
  document.querySelectorAll('[data-category]').forEach(b=>b.classList.toggle('selected',b.dataset.category===category));
  $('services').innerHTML=services.filter(s=>s.category===category).map(s=>`<article><span class="badge">${esc(s.operator)}</span><h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><p class="muted">${[269224,269226,269228].includes(s.token_id)?'审核参考价 0.5 U，实际以新签名报价为准；预计时间不等于退款时间。':'价格和预计时间须重新取得有效签名报价。'}</p><p>${s.submitted_evidence.length ? '已有提交结果：'+esc(s.submitted_evidence.join(', '))+'；不等于已结算或成功率。' : '暂无本市场已验证交付样本。'}</p>${s.availability?.failure?`<p>${esc(s.availability.failure.reason)}</p>`:''}${s.availability?`<p>报价探测：${esc(({quote_verified:'样例签名报价通过',unavailable:'当前未通过报价检查',paused:'已暂停',stale:'探测过期',unchecked:'等待检查'})[s.availability.state])}${s.availability.price_display?' · '+esc(s.availability.price_display):''}${s.availability.checked_at?' · '+esc(new Date(s.availability.checked_at*1000).toLocaleString()):''}。实际输入仍须重新报价。</p>`:''}${s.pause?`<p>${esc(s.pause)}</p>`:s.availability?.can_request_quote?`<a class="action" href="${esc(s.hire_url)}">查看报价与购买条件</a>`:'<p>当前暂不可购买，请稍后刷新查看。</p>'}<p class="muted">能力：${esc(({calculation_only:'单次计算',analysis_only:'分析建议'})[s.scope]||s.scope)} · 完成率：样本不足</p></article>`).join('')+`<article><h3>先检查是否适合你的任务</h3><p>查看真实数据、费用假设、验收条件和能力限制。</p><a class="action" href="/arena">打开任务分析</a></article>`;
}
function actionForm(w) {
  if (w.kind==='order') return '';
  const fields = w.kind==='lp'?'<label>目标区间半宽（价格刻度）<input name="half_width_ticks" type="number" min="1" max="100000" value="600" required></label><label>允许滑点 / 基点（100 基点 = 1%）<input name="slippage_bps" type="number" min="0" max="500" value="50" required></label><label class="check"><input type="checkbox" name="simulate_lp_exit">在节点只读试算移出和领取，不发送交易</label>':w.kind==='health'?'<label>假设抵押物跌幅 / %<input name="collateral_drop_pct" type="number" min="0" max="90" value="20" required></label><label>假设债务价格涨幅 / %<input name="debt_rise_pct" type="number" min="0" max="200" value="10" required></label><label>偿还资产<select name="venue"><option value="venus-core-usdt">Venus USDT</option><option value="venus-core-usdc">Venus USDC</option></select></label><label>准备偿还多少代币（可留空，仅做压力检查）<input name="amount" inputmode="decimal" placeholder="实际代币数量，不是美元估值"></label>':w.kind==='grid'?'<label>计划档数<input name="levels" type="number" min="2" max="50" value="10" required></label><label>假设资金 / 美元<input name="capital" type="number" min="0.01" max="1000000" step="any" value="1000" required></label><label>每次订单假设链上费用 / 美元<input name="gas_per_order" type="number" min="0" max="1000" value="0.2" step="any" required></label><label>每侧假设滑点 / 基点<input name="slippage_bps" type="number" min="0" max="500" value="50" required></label>':'<p>重新读取两个 Venus 市场的利率、可用现金、存入余量及暂停状态，并沿用本任务的资金、天数和成本假设。</p>';
  return `<details><summary>准备下一步怎么处理</summary><form data-action-form="${w.id}">${fields}<label class="check"><input name="consent" type="checkbox" required>同意读取公开数据并保存行动准备；不会替我交易</label><button>读取并准备行动</button><p>结果包含条件、阻碍和必要时的未签名草稿。当前没有发送这些草稿的入口，模拟通过也不代表已经执行。</p></form></details>`;
}
function actionResult(w) {
  const plan=w.events.find(e=>e.kind==='action_plan')?.data;
  if (!plan) return '';
  const old=Date.now()/1000>plan.valid_until;
  const n=v=>v===null||v===undefined?'—':Number(v).toLocaleString(undefined,{maximumFractionDigits:5});
  let facts='';
  if (plan.kind==='health') facts=`<p>当前健康系数 ${n(plan.metrics.current_health_factor)}；假设冲击后 ${n(plan.metrics.stressed_health_factor)}；压力情景外部偿还需求 ${n(plan.metrics.required_external_repay_usd)} 美元。</p>`;
  if (plan.kind==='lp') facts=`<p>目标价格刻度区间 ${esc(plan.metrics.target_lower_tick)} ～ ${esc(plan.metrics.target_upper_tick)}。保持相同流动性的理论资产差额：代币 0 为 ${n(plan.metrics.inventory_delta.token0)}，代币 1 为 ${n(plan.metrics.inventory_delta.token1)}。这不是新建仓位报价。</p>`;
  if (plan.kind==='grid') facts=`<p>每档假设资金 ${n(plan.metrics.capital_per_level_usd)} 美元；一个相邻档位完整买卖后，模型净差额 ${n(plan.metrics.net_adjacent_cycle_usd)} 美元。没有实际成交，不是累计收益。</p>`;
  if (plan.kind==='yield') facts='<div class="result-table"><table><thead><tr><th>市场</th><th>可用现金 / 代币</th><th>可再存入 / 代币</th><th>存入 / 退出暂停</th></tr></thead><tbody>'+plan.capacity.markets.map(r=>`<tr><td>${esc(r.venue_id)}</td><td>${n(r.cash_token_units)}</td><td>${n(r.supply_room_token_units)}</td><td>${r.mint_paused?'是':'否'} / ${r.redeem_paused?'是':'否'}</td></tr>`).join('')+'</tbody></table></div><p>协议现金不是你自己的可退出余额；还须核查抵押限制和换币成本。</p>';
  return `<section class="action-result"><h4>${esc(plan.summary)}</h4><p>${old?'历史准备已过期，执行前必须重新读取':'短时观察有效；仍未取得交易授权'} · ${esc(new Date(plan.prepared_at).toLocaleString())}</p>${facts}<ol>${plan.steps.map(s=>`<li>${esc(s)}</li>`).join('')}</ol><p>待解决条件：${plan.blockers.length} 项。${plan.simulation?.passed?'节点只读模拟通过，未发送交易。':''}</p><ul>${plan.blockers.map(b=>`<li>${esc(b)}</li>`).join('')}</ul><button data-plan-export="${w.id}">下载完整行动准备</button><details><summary>检查条件与原始数据</summary><pre>${esc(JSON.stringify(plan,null,2))}</pre></details></section>`;
}

function deliveryTable(delivery) {
  if (!delivery) return '';
  if (!delivery.acceptance && delivery.verification?.content) return `<details open><summary>查看供应商原始结果（内容待验收）</summary><p>文件哈希核验不代表结论正确。请核对任务输入、计算和实际用途；不要据此自动转账。</p><pre>${esc(delivery.verification.content)}</pre></details>`;
  if (!delivery.acceptance?.passed) return '';
  try {
    const result=JSON.parse(delivery.verification.content);
    if (!Array.isArray(result.buys)||!Array.isArray(result.sells)) return '';
    return `<details open><summary>查看已验收的网格计算结果</summary><p>输入参考价 ${esc(result.mark)}，假设资金 ${esc(result.budgetUsd)} 美元。这是计算价格表，未实际下单；参考价不是现在的市场价格。</p><div class="result-table"><table><thead><tr><th>方向</th><th>价格</th><th>每档美元</th><th>数量</th></tr></thead><tbody>${[...result.buys,...result.sells].map(row=>`<tr><td>${row.side==='buy'?'买入':'卖出'}</td><td>${esc(row.price)}</td><td>${esc(row.sizeUsd)}</td><td>${esc(row.amount)}</td></tr>`).join('')}</tbody></table></div><p>下面可填写这些结果对你的实际任务是否有帮助；计算正确不等于值得付费或保证收益。</p></details>`;
  } catch (_) { return ''; }
}
function display() {
  $('notificationPanel').hidden=!credential; $('forms').hidden=!credential; $('create').hidden=!!credential; $('backup').hidden=!credential; $('export').hidden=!credential; $('switchSpace').hidden=!credential;
  $('workspaceState').textContent=credential?'私有工作台已连接。请保存恢复凭证；不要把它放进公开提交材料。':'还没有创建私有工作台。';
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
      const detail=obs ? (w.kind==='yield'?`按假设净收益较高：${latest.comparison.best_under_assumptions}；退出与容量仍未知`:w.kind==='grid'?`池内价格：${Number(obs.price_usdt_per_wbnb).toFixed(4)} USDT/WBNB；${latest.in_range?'范围内':'范围外'}`:w.kind==='health'?`健康系数：${obs.health_factor??'无债务'}；目标所需偿还：${latest.repay_to_target_usd} 美元`:`当前 tick ${obs.current_tick}，区间 ${obs.lower_tick}～${obs.upper_tick}；${latest.in_range?'区间内':'区间外'}`) : latest.chain ? `订单 ${latest.chain.job_id} · ${latest.chain.budget_u} U · ${latest.chain.status}` : latest.error||'等待服务器首次读取';
      return `<article class="watch ${esc(w.state)}"><span class="badge">${stale?'数据过期，请检查服务':esc(w.state)}${!w.active?' · 已停止监控':''}</span><h3>${esc(w.kind==='order'?'订单 #'+w.spec.job_id:w.kind==='health'?'借贷账户检查':w.kind==='grid'?'网格范围监控':w.kind==='yield'?'收益持续比较':'LP 仓位 #'+w.spec.position_id)}</h3><p>${esc(detail)}</p>${historicDelivery?`<p>以下为历史交付记录（${esc(new Date(priorDelivery.at*1000).toLocaleString())}）；当前读取失败或尚未重新核验，不代表当前链上状态。</p>`:''}${deliveryTable(delivery)}${actionResult(w)}${actionForm(w)}${quality?`<p>计算验收：${quality.passed?'通过':'未通过：'+esc(quality.failures.join('; '))}；人工质量评价未完成。</p>`:''}<p>${unread?'有 '+unread+' 条未读提醒':'没有未读提醒'} · 最近检查 ${esc(lastObservation?new Date(lastObservation.at*1000).toLocaleString():'尚未读取')} · 服务到期 ${esc(new Date(w.expires*1000).toLocaleString())}</p>${w.kind==='order'?`<a class="action" href="/hire-live?job_id=${w.spec.job_id}">恢复订单、验收或退款</a>`:'<a class="action" href="/arena">分析下一步</a>'} <button data-ack="${w.id}">标记已读</button> ${w.active?`<button data-pause="${w.id}">暂停跟进</button>`:`<button data-resume="${w.id}">重新开启跟进</button>`}<details><summary>记录结果是否有用</summary><form data-feedback-form="${w.id}"><label>对你的任务有帮助吗？<select name="useful"><option value="not_reviewed">尚未判断</option value="yes">有帮助</option><option value="partly">部分有帮助</option><option value="no">没有帮助</option></select></label><label>说明具体帮助或问题<textarea name="comment" maxlength="1500" required></textarea></label><label>相同服务和价格下是否愿意再次购买？<select name="repurchase"><option value="unknown">尚未决定 / 未付费</option><option value="yes">愿意</option><option value="no">不愿意</option></select></label><label class="check"><input name="used_ai" type="checkbox">这段评价使用过 AI 辅助</label><button>保存本人评价</button><p class="muted">这是工作台使用者反馈，未经独立身份认证，不计为独立盲评。</p></form></details><details><summary>原始观察与时间记录（最近 300 条）</summary><pre>${esc(JSON.stringify(w.events,null,2))}</pre></details></article>`;
    }).join('')||'<p>还没有任务。添加一个公开订单或监控对象。</p>';
  } catch(e){message(e.message);} finally{busy=false;}
}
$('create').onclick=async()=>{try{credential=await api('/spaces',{});localStorage.setItem(key,JSON.stringify(credential));display();await refresh();await refreshNotifications();}catch(e){message(e.message);}};
$('backup').onclick=()=>download('safehire-private-recovery.json',credential);
$('restore').onchange=async e=>{try{const file=e.target.files[0];if(!file||file.size>4096)throw new Error('请选择小于 4 KB 的恢复凭证');const value=JSON.parse(await file.text());if(!/^[a-f0-9]{32}$/.test(value.space_id)||typeof value.token!=='string'||value.token.length<32||value.token.length>128)throw new Error('恢复凭证无效');credential=value;await api('/spaces/'+value.space_id,undefined,true);localStorage.setItem(key,JSON.stringify(value));display();await refresh();await refreshNotifications();}catch(err){credential=null;display();message(err.message);}};
$('export').onclick=()=>current&&download('safehire-service-records.json',current);
$('refresh').onclick=refresh;
for(const kind of ['order','health','lp','grid','yield']) $(kind+'Form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target), body={kind,consent:f.has('consent')};if(kind==='order'){body.job_id=Number(f.get('job_id'));body.notify_provider=f.has('notify_provider');}if(kind==='health'){body.account=f.get('account');body.threshold=Number(f.get('threshold'));body.target=Number(f.get('target'));}if(kind==='lp')body.position_id=Number(f.get('position_id'));if(kind==='grid'){body.lower=Number(f.get('lower'));body.upper=Number(f.get('upper'));}if(kind==='yield'){for(const n of ['capital','days','cost','minimum_gain'])body[n]=Number(f.get(n));body.current_venue=f.get('current_venue');}try{await api('/spaces/'+credential.space_id+'/watches',body,true);await refresh();message('已保存。服务器会继续检查；可在此查看记录或暂停。');}catch(err){message(err.message);}};
$('watches').onclick=async e=>{const b=e.target.closest('button');if(!b || (!b.dataset.pause && !b.dataset.ack && !b.dataset.resume && !b.dataset.planExport))return;try{if(b.dataset.planExport){const w=current.watches.find(w=>w.id===b.dataset.planExport);return download('safehire-action-preparation.json',w.events.find(e=>e.kind==='action_plan').data);}if(b.dataset.resume)await api(`/spaces/${credential.space_id}/watches/${b.dataset.resume}/resume`,{},true);if(b.dataset.pause)await api(`/spaces/${credential.space_id}/watches/${b.dataset.pause}/pause`,{},true);if(b.dataset.ack)await api(`/spaces/${credential.space_id}/watches/${b.dataset.ack}/acknowledge`,{},true);await refresh();}catch(err){message(err.message);}};
$('compareForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);const body={consent:f.has('consent')};for(const n of ['price','budgetUsd','levels','spanPct'])body[n]=Number(f.get(n));const button=e.target.querySelector('button');button.disabled=true;try{const r=await api('/compare-grid',body);$('comparison').innerHTML=r.offers.map(o=>`<p><strong>${esc(o.name)}</strong>：${o.quote?esc(o.quote.quote.price_display)+'，预计 '+esc(o.quote.quote.estimated_completion_seconds)+' 秒；签名已核验，尚未购买':esc(o.error||o.reason)}</p>`).join('');}catch(err){message(err.message);}finally{button.disabled=false;}};
document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>showServices(b.dataset.category));
(async()=>{display();try{const [cap,list]=await Promise.all([api('/capabilities'),api('/services')]);$('runtime').textContent=cap.server_followup?'服务器跟进运行中 · 约每 5 分钟读取 · 不自动转账':cap.enabled?'跟进进程当前不可用；请稍后刷新，暂时不要依赖监控。':'当前部署未开启服务器跟进；购买与公开证据仍可查看。';services=list.services;showServices('grid_trading');await refresh();await refreshNotifications();}catch(e){message(e.message);}setInterval(refresh,30000);})();

$('watches').addEventListener('submit', async e => {
  const form = e.target.closest('[data-feedback-form]'); if (!form) return; e.preventDefault();
  const f = new FormData(form);
  try { await api(`/spaces/${credential.space_id}/watches/${form.dataset.feedbackForm}/feedback`,
    {useful:f.get('useful'), comment:f.get('comment'), used_ai:f.has('used_ai'), repurchase:f.get('repurchase')},true);
    message('已保存本人反馈；不是独立评审或钱包身份认证。'); await refresh();
  } catch (error) { message(error.message); }
});

$('watches').addEventListener('submit', async e=>{
  const form=e.target.closest('[data-action-form]');if(!form)return;e.preventDefault();
  const f=new FormData(form),body={consent:f.has('consent')};
  for(const name of ['collateral_drop_pct','debt_rise_pct','half_width_ticks','slippage_bps','levels','capital','gas_per_order'])if(f.has(name))body[name]=Number(f.get(name));
  if(f.has('simulate_lp_exit'))body.simulate_lp_exit=true;
  if(f.get('amount')?.trim()){body.amount=f.get('amount').trim();body.venue=f.get('venue');}
  const button=form.querySelector('button');button.disabled=true;actionBusy=true;message('正在读取真实数据和检查条件，约需几十秒；不会发送交易。');
  try{await api(`/spaces/${credential.space_id}/watches/${form.dataset.actionForm}/action-plan`,body,true);actionBusy=false;button.disabled=false;button.focus();await refresh();message('行动准备已保存，请看检查结果与待解决条件。');}catch(error){message(error.message);}finally{actionBusy=false;if(button.isConnected)button.disabled=false;}
});
setInterval(async()=>{try{services=(await api('/services')).services;showServices(selectedCategory);}catch(_){services=services.map(s=>({...s,availability:{state:'stale',can_request_quote:false}}));showServices(selectedCategory);}},60000);

$('switchSpace').onclick=()=>{credential=null;current=null;localStorage.removeItem(key);$('watches').innerHTML='';display();message('已退出本机连接，服务器记录仍保留；可用恢复文件重新连接。');};

async function refreshNotifications(){
  if(!credential)return;
  try{const n=await api(`/spaces/${credential.space_id}/notifications`,undefined,true);
    $('notificationState').textContent=n.enabled?'手机提醒已启用；下面区分推送服务接收与本人阅读。':n.bound?'设备已绑定，等待手机验证码确认。':'尚未绑定手机提醒。';
    $('pushVerifyForm').hidden=!n.bound||n.verified; $('pushUnsubscribe').hidden=!n.bound;
    const labels={pending:'等待重试或发送',sending:'发送中',accepted_by_provider:'Bark 已接收，未证明本人阅读',failed:'发送失败，已停止重试',expired:'超过发送期限',cancelled:'已取消'};
    $('notificationLog').innerHTML=n.deliveries.map(r=>`<p>提醒 ${r.id}：${esc(labels[r.state]||r.state)} · 已尝试 ${r.attempts} 次</p>`).join('')||'<p>暂无推送记录。</p>';
  }catch(e){$('notificationState').textContent=e.message;}
}
$('pushBindForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target),b=e.target.querySelector('button');b.disabled=true;try{const r=await api(`/spaces/${credential.space_id}/notifications/bind`,{device_key:f.get('device_key').trim(),consent:f.has('consent')},true);e.target.reset();message(r.provider_accepted?'验证通知已交给 Bark，请查看手机并填写验证码。':'Bark 未接受验证通知，请检查设备 Key 后重试。');await refreshNotifications();}catch(err){message(err.message);}finally{b.disabled=false;}};
$('pushVerifyForm').onsubmit=async e=>{e.preventDefault();try{await api(`/spaces/${credential.space_id}/notifications/verify`,{code:new FormData(e.target).get('code')},true);e.target.reset();await refreshNotifications();message('手机接收验证通过，已开启后续新提醒。');}catch(err){message(err.message);}};
$('pushUnsubscribe').onclick=async()=>{try{await api(`/spaces/${credential.space_id}/notifications/unsubscribe`,{},true);await refreshNotifications();message('已关闭提醒并删除服务器上的设备凭证。');}catch(err){message(err.message);}};
setInterval(refreshNotifications,30000);
