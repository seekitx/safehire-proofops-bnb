"""Deterministic, caller-snapshot models; never orders, chain proofs or backtests.

LP formulas use raw token1/token0 ticks, then apply token decimals for display.
Grid is a single fully-filled adjacent cycle, not cumulative strategy performance.
Yield compares with staying in the current venue, not a fictitious zero-return cash leg.
Health uses user-supplied thresholds and simultaneous asset shocks, not a live oracle.
"""
from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal, localcontext
from typing import Any

from proofops.arena.models import Proposal, TaskSpec, utcnow


def D(value: Any) -> Decimal:
    return Decimal(str(value))


def number(value: Decimal) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError('calculation exceeds supported numeric range')
    return result


def lp_inventory(tick: int, lower: int, upper: int, liquidity: int,
                 decimals0: int, decimals1: int) -> dict[str, str]:
    if not -887272 <= lower < upper <= 887272 or not -887272 <= tick <= 887272:
        raise ValueError('invalid v3 tick range')
    with localcontext() as ctx:
        ctx.prec = 60
        a, b, p = [D('1.0001') ** (D(t) / 2) for t in (lower, upper, tick)]
        p = min(b, max(a, p))
        amount0 = D(liquidity) * (b - p) / (p * b) / (D(10) ** decimals0)
        amount1 = D(liquidity) * (p - a) / (D(10) ** decimals1)
        return {'token0': str(amount0), 'token1': str(amount1),
                'basis': 'fixed_liquidity_theoretical_inventory_not_mint_quote'}


def lp_range(i: dict[str, Any]) -> tuple[int, int]:
    spacing = i['tick_spacing']
    lower = math.floor((i['current_tick'] - i['half_width_ticks']) / spacing) * spacing
    upper = math.ceil((i['current_tick'] + i['half_width_ticks']) / spacing) * spacing
    lower = max(math.ceil(-887272 / spacing) * spacing, lower)
    upper = min(math.floor(887272 / spacing) * spacing, upper)
    if not lower <= i['current_tick'] < upper:
        raise ValueError('requested range cannot contain current tick within protocol bounds')
    return lower, upper


def grid_metrics(i: dict[str, Any]) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = 40
        ratio = (D(i['upper_price']) / D(i['lower_price'])) ** (D(1) / (i['levels'] - 1))
        fee = (D(i['fee_bps_per_side']) + D(i['transfer_tax_bps_per_side']) + D(i['slippage_bps_per_side'])) / 10000
        allocation = D(i['capital_usd']) / i['levels']
        gas = D(i['gas_usd_per_order'])
        # Budget includes the entry cost; exit pays the modeled cost again.
        net = allocation * ratio * (1 - fee) / (1 + fee) - allocation - 2 * gas
        cost = allocation * ratio - allocation - net
        prices = [number(D(i['lower_price']) * ratio**n) for n in range(i['levels'])]
        return {'prices': prices, 'capital_per_level_usd': number(allocation),
                'net_adjacent_cycle_usd': number(net), 'cycle_cost_usd': number(cost),
                'break_even_ratio': number((1 + fee) / (1 - fee) * (1 + 2 * gas / allocation)),
                'cycle_model': 'one_fully_filled_adjacent_cycle', 'fills_observed': 0,
                'inventory_and_gap_risk_included': False}


def yield_metrics(i: dict[str, Any]) -> list[dict[str, Any]]:
    with localcontext() as ctx:
        ctx.prec = 40
        capital, horizon = D(i['capital_usd']), D(i['horizon_days']) / 365
        staying = capital * ((1 + D(i['current_apy_pct']) / 100) ** horizon - 1)
        rows = []
        for venue in i['venues']:
            gross = capital * ((1 + D(venue['apy_pct']) / 100) ** horizon - 1)
            edge = gross - staying - D(venue['migration_cost_usd'])
            rows.append({**venue, 'hold_income_usd': number(staying),
                         'route_income_usd': number(gross - D(venue['migration_cost_usd'])),
                         'improvement_vs_hold_usd': number(edge),
                         'capacity_sufficient': venue['capacity_usd'] >= i['capital_usd'],
                         'withdrawal_within_horizon': venue['withdrawal_delay_days'] <= i['horizon_days']})
        return sorted(rows, key=lambda row: (-row['improvement_vs_hold_usd'], row['venue_id']))


def health_metrics(i: dict[str, Any]) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = 40
        collateral = sum((D(a['value_usd']) * D(a['liquidation_threshold']) for a in i['collateral']), D(0))
        stressed = sum((D(a['value_usd']) * D(a['liquidation_threshold']) * (1 - D(a['price_drop_pct']) / 100)
                        for a in i['collateral']), D(0))
        debt = sum((D(a['value_usd']) for a in i['debts']), D(0))
        stressed_debt = sum((D(a['value_usd']) * (1 + D(a['price_rise_pct']) / 100) for a in i['debts']), D(0))
        required = max(D(0), stressed_debt - stressed / D(i['target_health_factor']))
        # Round UP at cents, never understate the modeled repay requirement.
        repay = required.quantize(D('.01'), rounding='ROUND_CEILING')
        repay = min(repay, stressed_debt)
        return {'health_factor_now': number(collateral / debt) if debt else None,
                'stressed_health_factor': number(stressed / stressed_debt) if stressed_debt else None,
                'no_debt': not bool(stressed_debt), 'weighted_collateral_stress_usd': number(stressed),
                'stressed_debt_usd': number(stressed_debt), 'required_repay_usd': number(repay),
                'repay_budget_sufficient': repay <= D(i['available_repay_usd'])}


def reference_proposal(task: TaskSpec) -> Proposal:
    i = task.inputs
    action, params = 'hold', {}
    if task.category == 'rebalancing':
        if not i['old_lower_tick'] <= i['current_tick'] < i['old_upper_tick']:
            lower, upper = lp_range(i)
            if i['estimated_cost_usd'] <= task.limits.max_cost_usd and i['slippage_bps'] <= task.limits.max_slippage_bps:
                action, params = 'reset_lp_range', {'lower_tick': lower, 'upper_tick': upper}
    elif task.category == 'grid_trading':
        m = grid_metrics(i)
        if m['net_adjacent_cycle_usd'] > 0 and m['cycle_cost_usd'] <= task.limits.max_cost_usd and i['slippage_bps_per_side'] <= task.limits.max_slippage_bps:
            action, params = 'plan_grid', {'prices': m['prices'], 'stop_price': i['stop_price']}
    elif task.category == 'yield_optimisation':
        good = [v for v in yield_metrics(i) if v['improvement_vs_hold_usd'] > i['min_improvement_usd']
                and v['capacity_sufficient'] and v['withdrawal_within_horizon']
                and v['migration_cost_usd'] <= task.limits.max_cost_usd]
        if good:
            action, params = 'route_yield', {'venue_id': good[0]['venue_id']}
    else:
        m = health_metrics(i)
        if m['required_repay_usd'] > 0 and m['repay_budget_sufficient'] and i['estimated_cost_usd'] <= task.limits.max_cost_usd:
            action, params = 'repay', {'repay_usd': m['required_repay_usd']}
    return Proposal(agent_ref='local:reference-v2', task_hash=task.task_hash,
                    snapshot_hash=task.snapshot_hash, action=action, parameters=params)


def evaluate(task: TaskSpec, proposal: Proposal, *, now: datetime | None = None) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}

    def check(name: str, condition: bool, detail: str = '') -> None:
        checks.append({'name': name, 'passed': bool(condition), 'detail': detail})

    check('same_task', proposal.task_hash == task.task_hash)
    check('same_snapshot', proposal.snapshot_hash == task.snapshot_hash)
    check('fresh_snapshot', task.fresh(now), 'Caller timestamps are checked, not authenticated as chain data.')
    i, p = task.inputs, proposal.parameters
    reference = reference_proposal(task)
    if proposal.action == 'hold':
        check('hold_is_policy_consistent', reference.action == 'hold')
        check('hold_has_no_parameters', not p)
        if task.category == 'health_factor_monitoring':
            metrics = health_metrics(i)
            check('protection_target_resolved', metrics['required_repay_usd'] == 0,
                  'Insufficient repay budget is an unresolved risk, not successful protection.')
        if task.category == 'rebalancing':
            check('range_target_resolved', i['old_lower_tick'] <= i['current_tick'] < i['old_upper_tick'],
                  'A cost/slippage-limited hold leaves an out-of-range LP unresolved; it is not a successful reset.')
        metrics['modeled_cost_usd'] = 0
    elif task.category == 'rebalancing':
        check('category_action', proposal.action == 'reset_lp_range')
        check('parameter_schema', set(p) == {'lower_tick', 'upper_tick'})
        lower, upper = p.get('lower_tick'), p.get('upper_tick')
        valid = type(lower) is int and type(upper) is int and -887272 <= lower < upper <= 887272
        check('protocol_tick_bounds', valid)
        if valid:
            check('tick_spacing', lower % i['tick_spacing'] == 0 and upper % i['tick_spacing'] == 0)
            check('spot_inside_target', lower <= i['current_tick'] < upper)
            target = lp_range(i)
            check('requested_range_policy', (lower, upper) == target,
                  'This version enforces the requested width; it does not optimize future price forecasts.')
            check('avoid_unnecessary_churn', not i['old_lower_tick'] <= i['current_tick'] < i['old_upper_tick'])
            old = lp_inventory(i['current_tick'], i['old_lower_tick'], i['old_upper_tick'], i['liquidity_raw'], i['token0_decimals'], i['token1_decimals'])
            new = lp_inventory(i['current_tick'], lower, upper, i['liquidity_raw'], i['token0_decimals'], i['token1_decimals'])
            metrics = {'inventory_before': old, 'inventory_target_same_liquidity': new,
                       'token0_delta': str(D(new['token0']) - D(old['token0'])),
                       'token1_delta': str(D(new['token1']) - D(old['token1'])),
                       'range_before': [i['old_lower_tick'], i['old_upper_tick']], 'range_after': [lower, upper],
                       'funding_sufficiency_verified': False}
        check('cost_cap', i['estimated_cost_usd'] <= task.limits.max_cost_usd)
        check('slippage_cap', i['slippage_bps'] <= task.limits.max_slippage_bps)
        metrics['modeled_cost_usd'] = i['estimated_cost_usd']
    elif task.category == 'grid_trading':
        metrics = grid_metrics(i)
        check('category_action', proposal.action == 'plan_grid')
        check('parameter_schema', set(p) == {'prices', 'stop_price'})
        prices = p.get('prices')
        valid = isinstance(prices, list) and len(prices) == i['levels'] and all(type(v) in (int, float) and math.isfinite(v) for v in prices)
        check('order_count_and_numbers', valid)
        if valid:
            check('grid_geometry', all(math.isclose(a, b, rel_tol=1e-10, abs_tol=1e-14) for a, b in zip(prices, metrics['prices'], strict=True)))
        stop = p.get('stop_price')
        check('stop_price', type(stop) in (int, float) and stop == i['stop_price'])
        check('positive_net_cycle', metrics['net_adjacent_cycle_usd'] > 0)
        check('cycle_cost_cap', metrics['cycle_cost_usd'] <= task.limits.max_cost_usd)
        check('slippage_cap', i['slippage_bps_per_side'] <= task.limits.max_slippage_bps)
        metrics['modeled_cost_usd'] = metrics['cycle_cost_usd']
    elif task.category == 'yield_optimisation':
        check('category_action', proposal.action == 'route_yield')
        check('parameter_schema', set(p) == {'venue_id'})
        rows = yield_metrics(i)
        selected = next((v for v in rows if v['venue_id'] == p.get('venue_id')), None)
        check('approved_venue', selected is not None)
        if selected:
            metrics = dict(selected)
            check('improves_on_current_venue', selected['improvement_vs_hold_usd'] > i['min_improvement_usd'])
            check('capacity', selected['capacity_sufficient'])
            check('withdrawal_horizon', selected['withdrawal_within_horizon'])
            check('cost_cap', selected['migration_cost_usd'] <= task.limits.max_cost_usd)
            metrics['modeled_cost_usd'] = selected['migration_cost_usd']
    else:
        metrics = health_metrics(i)
        check('category_action', proposal.action == 'repay')
        check('parameter_schema', set(p) == {'repay_usd'})
        repay = p.get('repay_usd')
        valid = type(repay) in (int, float) and math.isfinite(repay) and 0 <= repay <= metrics['stressed_debt_usd']
        check('repay_value', valid)
        if valid:
            check('repay_budget', repay <= i['available_repay_usd'])
            check('target_reached', D(repay) >= D(metrics['required_repay_usd']))
            check('avoid_unnecessary_repay', metrics['required_repay_usd'] > 0)
            remaining = D(metrics['stressed_debt_usd']) - D(repay)
            metrics['modeled_health_after'] = number(D(metrics['weighted_collateral_stress_usd']) / remaining) if remaining else None
            metrics['debt_cleared'] = not bool(remaining)
        check('cost_cap', i['estimated_cost_usd'] <= task.limits.max_cost_usd)
        metrics['modeled_cost_usd'] = i['estimated_cost_usd']
    return {'schema_version': 'safehire-acceptance/2', 'evaluated_at': (now or utcnow()).isoformat(), 'task_hash': task.task_hash,
            'proposal_hash': proposal.proposal_hash, 'agent_ref': proposal.agent_ref,
            'policy_accepted': all(c['passed'] for c in checks), 'checks': checks, 'metrics': metrics,
            'evidence_mode': 'caller_supplied_model_validation', 'trade_executed': False,
            'chain_snapshot_verified': False, 'agent_authorship_verified': False,
            'quality_review_scope': 'deterministic_constraints_only',
            'not_proven': ['real_world_profit', 'independent_review', 'paid_delivery', 'execution_authority']}


def compare(task: TaskSpec, proposals: list[Proposal], *, now: datetime | None = None) -> dict[str, Any]:
    if not 2 <= len(proposals) <= 3 or len({p.agent_ref for p in proposals}) != len(proposals):
        raise ValueError('compare two or three distinct agent references on one task')
    reports = [evaluate(task, proposal, now=now) for proposal in proposals]
    eligible = [r for r in reports if r['policy_accepted']]
    # No paid ranking, arbitrary trust score, or inferred business independence.
    return {'task_hash': task.task_hash, 'reports': reports,
            'eligible_agent_refs': [r['agent_ref'] for r in eligible],
            'winner': None, 'reason': 'Constraint eligibility is not measured provider quality or profit.',
            'same_inputs': True, 'independent_businesses_verified': False}
