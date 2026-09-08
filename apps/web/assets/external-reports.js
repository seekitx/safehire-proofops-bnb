'use strict';
(() => {
  const $ = id => document.getElementById(id);
  if (!$('external-lp-run')) return;
  let receipt = null;
  const key = 'safehire-external-lp-report-v1';
  const show = value => {
    receipt = value;
    const report = value.report;
    $('external-lp-summary').textContent = `Position ${report.position}: ${report.in_range ? 'inside its range' : 'outside its range'}. ${report.verdict || ''} Supplier measured ${report.measured_at}. Received in ${value.elapsed_seconds}s. Service fee: 0. This is an unsigned supplier report, not an independently verified recommendation.`;
    $('external-lp-raw').textContent = value.raw_text;
    $('external-lp-export').disabled = false;
  };
  try {
    const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
    if (saved?.schema_version === 'safehire-external-report/1' && saved.report && saved.raw_text) {
      show(saved);
      $('external-lp-state').textContent = 'Recovered prior report from this tab. Its original time is shown; run again for a current reading.';
    }
  } catch (_) { try { sessionStorage.removeItem(key); } catch (_) {} }
  $('external-lp-run').onclick = async () => {
    if (!$('external-lp-position').reportValidity()) return;
    if (!$('external-lp-consent').checked) {
      $('external-lp-state').textContent = 'Approve sending this public position number to Brain first.'; return;
    }
    $('external-lp-run').disabled = true;
    $('external-lp-export').disabled = true;
    receipt = null;
    try { sessionStorage.removeItem(key); } catch (_) {}
    $('external-lp-summary').textContent = '';
    $('external-lp-raw').textContent = '';
    $('external-lp-state').textContent = 'Request sent to Brain. Waiting up to 30 seconds; no wallet or payment is involved…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 35000);
    try {
      const response = await fetch('/api/arena/external-reports/lp', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, cache: 'no-store',
        signal: controller.signal,
        body: JSON.stringify({position_id: Number($('external-lp-position').value), consent_send_position: true})
      });
      const value = await response.json();
      if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Report unavailable');
      show(value);
      $('external-lp-state').textContent = 'Report received. Review the result and download its original supplier text.';
      try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {
        $('external-lp-state').textContent += ' Browser recovery unavailable; download before leaving.';
      }
    } catch (error) {
      $('external-lp-state').textContent = error.name === 'AbortError' ? 'Supplier timed out. No payment made. Retry when ready.' : error.message;
    } finally { clearTimeout(timer); $('external-lp-run').disabled = false; }
  };
  $('external-lp-export').onclick = () => {
    if (!receipt) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(receipt, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url;
    link.download = `safehire-readonly-position-${receipt.requested_position_id}.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  let health = null;
  $('health-read').onclick = async () => {
    if (!$('health-account').reportValidity()) return;
    if (!$('health-consent').checked) { $('health-state').textContent = 'Approve the public account read first.'; return; }
    $('health-read').disabled = true; $('health-export').disabled = true; health = null;
    $('health-result').textContent = ''; $('health-state').textContent = 'Reading Venus markets and checking totals…';
    const controller = new AbortController(); const timer = setTimeout(() => controller.abort(), 55000);
    try {
      const response = await fetch('/api/arena/sources/venus-health', {method: 'POST',
        headers: {'Content-Type': 'application/json'}, cache: 'no-store', signal: controller.signal,
        body: JSON.stringify({account: $('health-account').value.trim(), consent_read_public_account: true})});
      const value = await response.json();
      if (!response.ok) throw new Error(typeof value.detail === 'string' ? value.detail : 'Account read rejected');
      health = value;
      $('health-state').textContent = `Block ${value.block_number}: ${value.status}. Health ratio: ${value.health_factor ?? 'no debt'}. This is not a guarantee against liquidation.`;
      $('health-result').textContent = JSON.stringify({account: value.account, markets: value.markets,
        collateral_usd: value.collateral_usd, debt_usd: value.debt_usd,
        protocol_net_liquidity_usd: value.protocol_net_liquidity_usd, boundary: value.boundary}, null, 2);
      $('health-export').disabled = false;
    } catch (error) { $('health-state').textContent = error.name === 'AbortError' ? 'Source timed out; no transaction attempted.' : error.message; }
    finally { clearTimeout(timer); $('health-read').disabled = false; }
  };
  $('health-export').onclick = () => {
    if (!health) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(health, null, 2)], {type: 'application/json'}));
    const link = document.createElement('a'); link.href = url; link.download = 'safehire-venus-health-source.json'; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
})();
