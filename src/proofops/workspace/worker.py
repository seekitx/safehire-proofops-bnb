from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from proofops.arena.financial_sources import observe_venus
from proofops.arena.health_sources import observe_health
from proofops.arena.lp_sources import observe_lp
from proofops.services.live_erc8183 import live_delivery, live_job_status, notify_live_agent
from proofops.workspace.market import observe_grid_market, yield_comparison
from proofops.workspace.store import Journal


async def process(journal: Journal, root: Path, row: dict[str, Any]) -> None:
    attempted = False
    try:
        spec = row['spec']
        if row['kind'] == 'order':
            status = await live_job_status(job_id=spec['job_id'])
            result: dict[str, Any] = {'observed_at': time.time(), 'chain': status, 'transaction_sent': False}
            phase = str(status['status']).lower()
            if phase == 'funded':
                # Only explicitly opted-in jobs; at most three calls, never another payment.
                if spec['notify_provider'] and journal.reserve_notification(spec['job_id']):
                    attempted = True
                    result['notification'] = await notify_live_agent(root, job_id=spec['job_id'])
                else:
                    result['notification'] = row['latest'].get('notification')
                result['refund_after'] = status['expired_at']
                result['internal_progress_verified'] = False
                eta_deadline = row['created'] + 600
                result['followup_wait_seconds'] = int(time.time()-row['created'])
                if time.time() > eta_deadline:
                    phase = 'overdue'
                    result['wait_notice'] = 'More than 10 minutes since tracking began. This is a follow-up threshold, not an onchain refund deadline.'
            if phase in {'submitted', 'completed'}:
                delivery = await live_delivery(job_id=spec['job_id'])
                result['delivery'] = delivery
                if delivery.get('acceptance') and not delivery['acceptance']['passed']:
                    phase = 'acceptance_failed'
            journal.finish(row['id'], phase, result, attempted=attempted,
                           terminal=phase in {'completed', 'rejected', 'expired'})
        elif row['kind'] == 'health':
            obs = await observe_health(spec['account'])
            hf = obs['health_factor']
            threshold = Decimal(str(spec['threshold']))
            triggered = hf is not None and Decimal(hf) < threshold
            target = Decimal(str(spec['target']))
            repay = max(Decimal(0), Decimal(obs['debt_usd'])-Decimal(obs['weighted_collateral_usd'])/target)
            journal.finish(row['id'], 'alert' if triggered else 'no_debt' if hf is None else 'observing',
                           {'observation': obs, 'threshold': str(threshold), 'repay_to_target_usd': str(repay),
                            'target': str(target), 'triggered': triggered, 'notification_channel': 'private_in_app_inbox',
                            'external_notification_sent': False, 'trade_executed': False})
        elif row['kind'] == 'lp':
            obs = await observe_lp(spec['position_id'])
            inside = obs['lower_tick'] <= obs['current_tick'] < obs['upper_tick']
            journal.finish(row['id'], 'observing' if inside else 'alert',
                           {'observation': obs, 'in_range': inside, 'triggered': not inside,
                            'notification_channel': 'private_in_app_inbox', 'trade_executed': False,
                            'next_action': 'Observe' if inside else 'Review reset cost and a new range in Arena; no reset executed'})
        elif row['kind'] == 'grid':
            obs = await observe_grid_market()
            price = Decimal(obs['price_usdt_per_wbnb'])
            inside = Decimal(str(spec['lower'])) <= price <= Decimal(str(spec['upper']))
            journal.finish(row['id'], 'observing' if inside else 'alert',
                           {'observation':obs, 'in_range':inside, 'triggered':not inside,
                            'trade_executed':False, 'orders_managed':False,
                            'notification_channel':'private_in_app_inbox',
                            'next_action':'Review your grid plan. This alert does not cancel orders or enforce a stop loss.'})
        elif row['kind'] == 'yield':
            obs = await observe_venus()
            comparison = yield_comparison(obs,spec)
            journal.finish(row['id'], 'alert' if comparison['triggered'] else 'observing',
                           {'observation':obs, 'comparison':comparison,
                            'notification_channel':'private_in_app_inbox', 'trade_executed':False})
        else:
            raise ValueError('Unsupported watch')
    except (httpx.HTTPError, ValueError, TypeError, KeyError, OverflowError) as exc:
        journal.finish(row['id'], 'error', {'error': str(exc)[:350], 'observed_at': time.time(),
                                          'risk_state': 'unknown', 'transaction_sent': False}, attempted=attempted)


async def run(journal: Journal, root: Path) -> None:
    while True:
        row = journal.claim()
        if row:
            try:
                async with asyncio.timeout(150):
                    await process(journal, root, row)
            except TimeoutError:
                journal.finish(row['id'], 'error', {'error': 'Source check timed out', 'risk_state': 'unknown'})
        else:
            await asyncio.sleep(5)
