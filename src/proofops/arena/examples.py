from __future__ import annotations

from typing import Any

from proofops.arena.models import TaskSpec, utcnow


def examples() -> dict:
    base = {'snapshot': {'chain_id': 56, 'block_number': 1, 'block_hash': '0x' + '0' * 64,
                         'observed_at': utcnow().isoformat(), 'source': 'SYNTHETIC_EXAMPLE_NOT_CHAIN_DATA'},
            'limits': {'max_cost_usd': 10, 'max_slippage_bps': 100, 'max_snapshot_age_seconds': 300}}
    inputs = {
        'rebalancing': {'current_tick': 300, 'old_lower_tick': -120, 'old_upper_tick': 120,
            'tick_spacing': 60, 'half_width_ticks': 180, 'liquidity_raw': 1000000000000000000,
            'token0_decimals': 18, 'token1_decimals': 18, 'estimated_cost_usd': 2, 'slippage_bps': 50},
        'grid_trading': {'current_price': 100, 'lower_price': 90, 'upper_price': 110,
            'levels': 8, 'capital_usd': 1000, 'fee_bps_per_side': 25, 'transfer_tax_bps_per_side': 0,
            'slippage_bps_per_side': 20, 'gas_usd_per_order': .02, 'stop_price': 85},
        'yield_optimisation': {'capital_usd': 1000, 'current_apy_pct': 5, 'horizon_days': 90,
            'min_improvement_usd': 1, 'venues': [
                {'venue_id': 'scenario-venue-a', 'apy_pct': 8, 'migration_cost_usd': 1, 'capacity_usd': 100000, 'withdrawal_delay_days': 0},
                {'venue_id': 'scenario-venue-b', 'apy_pct': 12, 'migration_cost_usd': 50, 'capacity_usd': 100000, 'withdrawal_delay_days': 0}]},
        'health_factor_monitoring': {'collateral': [{'asset': 'scenario-collateral', 'value_usd': 1000,
            'liquidation_threshold': .8, 'price_drop_pct': 20}],
            'debts': [{'asset': 'scenario-debt', 'value_usd': 600, 'price_rise_pct': 0}],
            'target_health_factor': 1.5, 'available_repay_usd': 200, 'estimated_cost_usd': 1}}
    return {'evidence_mode': 'synthetic_examples', 'live_provider_or_chain_calls': False,
            'tasks': {k: TaskSpec(category=k, inputs=v, **base).to_dict() for k, v in inputs.items()}}


def walkthrough(category: str) -> dict[str, Any]:
    """Two local test plans, never two providers or a measured agent advantage."""
    from proofops.arena.models import Proposal, TaskSpec
    from proofops.arena.planners import compare, reference_proposal

    if category not in examples()['tasks']:
        raise ValueError('unknown category')
    payload = examples()['tasks'][category]
    if category == 'yield_optimisation':
        payload['inputs']['venues'].append({'venue_id': 'high-apy-low-capacity', 'apy_pct': 20,
            'migration_cost_usd': 1, 'capacity_usd': 100, 'withdrawal_delay_days': 0})
    if category == 'health_factor_monitoring':
        payload['inputs']['debts'][0]['price_rise_pct'] = 2
    task = TaskSpec.model_validate(payload)
    good = reference_proposal(task)
    altered = good.model_dump(mode='json')
    altered['agent_ref'] = 'local:adversarial-fixture'
    narratives = {
        'rebalancing': 'An LP has left its earning range. Reject a replacement with ticks that violate pool spacing.',
        'grid_trading': 'A grid looks profitable before costs. Reject a proposal that silently removes the requested stop.',
        'yield_optimisation': 'A venue advertises the highest APY. Reject it when the full capital exceeds available capacity.',
        'health_factor_monitoring': 'Collateral drops while debt grows. Reject a repayment too small to restore the requested stressed health factor.',
    }
    if category == 'rebalancing':
        altered['parameters']['lower_tick'] += 1
    elif category == 'grid_trading':
        altered['parameters']['stop_price'] = task.inputs['upper_price']
    elif category == 'yield_optimisation':
        altered['parameters']['venue_id'] = 'high-apy-low-capacity'
    else:
        altered['parameters']['repay_usd'] = 0.01
    bad = Proposal.model_validate(altered)
    return {'evidence_mode': 'SYNTHETIC_WALKTHROUGH_NOT_PROVIDER_BENCHMARK',
            'narrative': narratives[category], 'task': task.to_dict(),
            'reference_proposal': good.model_dump(mode='json'),
            'counterexample_proposal': bad.model_dump(mode='json'),
            'comparison': compare(task, [good, bad]), 'real_provider_count': 0,
            'public_reputation_updated': False, 'funds_moved': False}
