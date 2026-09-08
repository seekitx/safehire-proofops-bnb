'use strict';
const $ = id => document.getElementById(id);
const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const key = 'safehire-workspace-v1';
let credential = null, current = null, services = [], busy = false;
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
  const selectedForm = {grid_trading:'grid', rebalancing:'lp', yield_optimisation:'yield', health_factor_monitoring:'health'}[category];
  for (const kind of ['grid','lp','yield','health']) $(kind+'Form').hidden = kind !== selectedForm;
  $('scope').textContent=scopes[category];
  document.querySelectorAll('[data-category]').forEach(b=>b.classList.toggle('selected',b.dataset.category===category));
  $('services').innerHTML=services.filter(s=>s.category===category).map(s=>`<article><span class="badge">${esc(s.operator)}</span><h3>${esc(s.name)}</h3><p>${esc(s.description)}</p><p class="muted">${s.token_id===269224?'审核参考价 0.5 U，实际以新签名报价为准；预计时间不等于退款时间。':'价格和预计时间须重新取得有效签名报价。'}</p><p>${s.submitted_evidence.length ? '已有提交结果：'+esc(s.submitted_evidence.join(', '))+'；不等于已结算或成功率。' : '暂无本市场已验证交付样本。'}</p>${s.pause?`<p>${esc(s.pause)}</p>`:`<a class="action" href="${esc(s.hire_url)}">查看报价与购买条件</a>`}<p class="muted">能力：${esc(s.scope)} · 完成率：样本不足</p></article>`).join('')+`<article><h3>先检查是否适合你的任务</h3><p>查看真实数据、费用假设、验收条件和能力限制。</p><a class="action" href="/arena">打开任务分析</a></article>`;
}
function display() {
  $('forms').hidden=!credential; $('create').hidden=!!credential; $('backup').hidden=!credential; $('export').hidden=!credential;
  $('workspaceState').textContent=credential?'私有工作台已连接。请保存恢复凭证；不要把它放进公开提交材料。':'还没有创建私有工作台。';
}
async function refresh() {
  if (!credential || busy || ($('watches').contains(document.activeElement) && document.activeElement.matches('input,textarea,select'))) return;
  busy=true;
  try {
    current=await api('/spaces/'+credential.space_id,undefined,true);
    $('watches').innerHTML=current.watches.map(w=>{
      const unread=w.events.filter(e=>e.kind==='alert'&&!e.read_at).length;
      const latest=w.latest; const obs=latest.observation;
      const lastObservation=w.events.find(e=>e.kind==='observation'||e.kind==='alert');
      const stale=!!w.active && Date.now()/1000-(lastObservation?.at||w.created)>600;
      const quality=latest.delivery?.acceptance;
      const detail=obs ? (w.kind==='yield'?`按假设净收益较高：${latest.comparison.best_under_assumptions}；退出与容量仍未知`:w.kind==='grid'?`池内价格：${Number(obs.price_usdt_per_wbnb).toFixed(4)} USDT/WBNB；${latest.in_range?'范围内':'范围外'}`:w.kind==='health'?`健康系数：${obs.health_factor??'无债务'}；目标所需偿还：${latest.repay_to_target_usd} 美元`:`当前 tick ${obs.current_tick}，区间 ${obs.lower_tick}～${obs.upper_tick}；${latest.in_range?'区间内':'区间外'}`) : latest.chain ? `订单 ${latest.chain.job_id} · ${latest.chain.budget_u} U · ${latest.chain.status}` : latest.error||'等待服务器首次读取';
      return `<article class="watch ${esc(w.state)}"><span class="badge">${stale?'数据过期，请检查服务':esc(w.state)}${!w.active?' · 已停止':''}</span><h3>${esc(w.kind==='order'?'订单 #'+w.spec.job_id:w.kind==='health'?'借贷账户检查':w.kind==='grid'?'网格范围监控':w.kind==='yield'?'收益持续比较':'LP 仓位 #'+w.spec.position_id)}</h3><p>${esc(detail)}</p>${quality?`<p>计算验收：${quality.passed?'通过':'未通过：'+esc(quality.failures.join('; '))}；人工质量评价未完成。</p>`:''}<p>${unread?'有 '+unread+' 条未读提醒':'没有未读提醒'} · 最近读取 ${esc(lastObservation?new Date(lastObservation.at*1000).toLocaleString():'尚未读取')} · 服务到期 ${esc(new Date(w.expires*1000).toLocaleString())}</p>${w.kind==='order'?`<a class="action" href="/hire-live?job_id=${w.spec.job_id}">恢复订单、验收或退款</a>`:'<a class="action" href="/arena">分析下一步</a>'} <button data-ack="${w.id}">标记已读</button> ${w.active?`<button data-pause="${w.id}">暂停跟进</button>`:''}<details><summary>记录结果是否有用</summary><form data-feedback-form="${w.id}"><label>对你的任务有帮助吗？<select name="useful"><option value="not_reviewed">尚未判断</option value="yes">有帮助</option><option value="partly">部分有帮助</option><option value="no">没有帮助</option></select></label><label>说明具体帮助或问题<textarea name="comment" maxlength="1500" required></textarea></label><label>相同服务和价格下是否愿意再次购买？<select name="repurchase"><option value="unknown">尚未决定 / 未付费</option><option value="yes">愿意</option><option value="no">不愿意</option></select></label><label class="check"><input name="used_ai" type="checkbox">这段评价使用过 AI 辅助</label><button>保存本人评价</button><p class="muted">这是工作台使用者反馈，未经独立身份认证，不计为独立盲评。</p></form></details><details><summary>原始观察与时间记录（最近 300 条）</summary><pre>${esc(JSON.stringify(w.events,null,2))}</pre></details></article>`;
    }).join('')||'<p>还没有任务。添加一个公开订单或监控对象。</p>';
  } catch(e){message(e.message);} finally{busy=false;}
}
$('create').onclick=async()=>{try{credential=await api('/spaces',{});localStorage.setItem(key,JSON.stringify(credential));display();await refresh();}catch(e){message(e.message);}};
$('backup').onclick=()=>download('safehire-private-recovery.json',credential);
$('restore').onchange=async e=>{try{const file=e.target.files[0];if(!file||file.size>4096)throw new Error('请选择小于 4 KB 的恢复凭证');const value=JSON.parse(await file.text());if(!/^[a-f0-9]{32}$/.test(value.space_id)||typeof value.token!=='string'||value.token.length<32||value.token.length>128)throw new Error('恢复凭证无效');credential=value;await api('/spaces/'+value.space_id,undefined,true);localStorage.setItem(key,JSON.stringify(value));display();await refresh();}catch(err){credential=null;display();message(err.message);}};
$('export').onclick=()=>current&&download('safehire-service-records.json',current);
$('refresh').onclick=refresh;
for(const kind of ['order','health','lp','grid','yield']) $(kind+'Form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target), body={kind,consent:f.has('consent')};if(kind==='order'){body.job_id=Number(f.get('job_id'));body.notify_provider=f.has('notify_provider');}if(kind==='health'){body.account=f.get('account');body.threshold=Number(f.get('threshold'));body.target=Number(f.get('target'));}if(kind==='lp')body.position_id=Number(f.get('position_id'));if(kind==='grid'){body.lower=Number(f.get('lower'));body.upper=Number(f.get('upper'));}if(kind==='yield'){for(const n of ['capital','days','cost','minimum_gain'])body[n]=Number(f.get(n));body.current_venue=f.get('current_venue');}try{await api('/spaces/'+credential.space_id+'/watches',body,true);await refresh();message('已保存。服务器会继续检查；可在此查看记录或暂停。');}catch(err){message(err.message);}};
$('watches').onclick=async e=>{const b=e.target.closest('button');if(!b || (!b.dataset.pause && !b.dataset.ack))return;try{if(b.dataset.pause)await api(`/spaces/${credential.space_id}/watches/${b.dataset.pause}/pause`,{},true);if(b.dataset.ack)await api(`/spaces/${credential.space_id}/watches/${b.dataset.ack}/acknowledge`,{},true);await refresh();}catch(err){message(err.message);}};
$('compareForm').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.target);const body={consent:f.has('consent')};for(const n of ['price','budgetUsd','levels','spanPct'])body[n]=Number(f.get(n));const button=e.target.querySelector('button');button.disabled=true;try{const r=await api('/compare-grid',body);$('comparison').innerHTML=r.offers.map(o=>`<p><strong>${esc(o.name)}</strong>：${o.quote?esc(o.quote.quote.price_display)+'，预计 '+esc(o.quote.quote.estimated_completion_seconds)+' 秒；签名已核验，尚未购买':esc(o.error||o.reason)}</p>`).join('');}catch(err){message(err.message);}finally{button.disabled=false;}};
document.querySelectorAll('[data-category]').forEach(b=>b.onclick=()=>showServices(b.dataset.category));
(async()=>{display();try{const [cap,list]=await Promise.all([api('/capabilities'),api('/services')]);$('runtime').textContent=cap.server_followup?'服务器跟进运行中 · 约每 5 分钟读取 · 不自动转账':cap.enabled?'跟进进程当前不可用；请稍后刷新，暂时不要依赖监控。':'当前部署未开启服务器跟进；购买与公开证据仍可查看。';services=list.services;showServices('grid_trading');await refresh();}catch(e){message(e.message);}setInterval(refresh,30000);})();

$('watches').addEventListener('submit', async e => {
  const form = e.target.closest('[data-feedback-form]'); if (!form) return; e.preventDefault();
  const f = new FormData(form);
  try { await api(`/spaces/${credential.space_id}/watches/${form.dataset.feedbackForm}/feedback`,
    {useful:f.get('useful'), comment:f.get('comment'), used_ai:f.has('used_ai'), repurchase:f.get('repurchase')},true);
    message('已保存本人反馈；不是独立评审或钱包身份认证。'); await refresh();
  } catch (error) { message(error.message); }
});
