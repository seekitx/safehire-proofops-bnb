"""Explicit conversion of public observations into calculator inputs."""
from __future__ import annotations

from typing import Any

from proofops.arena.financial_sources import observe_venus
from proofops.arena.health_sources import observe_health
from proofops.services.reviewed_calculators import inputs


async def prepare(token: int, account: str | None, capital: float) -> dict[str, Any]:
    if token == 269228:
        if not account:
            raise ValueError('Enter the public Venus Core account address to check.')
        observation = await observe_health(account)
        collateral = {}; debt = {}; prices = {}
        for index, market in enumerate(observation['markets']):
            name = f'market_{index}_USD'
            supplied = float(market['supplied_usd']); borrowed = float(market['borrowed_usd'])
            threshold = float(market['liquidation_threshold'])
            if supplied > 0 and threshold > 0:
                collateral[name] = {'amount': supplied, 'liqThreshold': threshold}
                prices[name] = 1
            if borrowed > 0:
                debt[name] = borrowed
                prices[name] = 1
        if not debt or not collateral:
            raise ValueError('This account has no comparable collateral and debt. Do not pay for an inapplicable calculation.')
        task = inputs(token, {'collateral': collateral, 'debt': debt, 'prices': prices})
        boundary = 'Markets are converted to dollar-denominated shares with unit price 1 solely to reproduce the health factor. This is not a real token price; provider per-asset liquidation prices are not token sell prices. Prices, interest and parameters can change after this snapshot.'
    else:
        observation = await observe_venus()
        task = inputs(token, {'pools': {r['venue_id']: {'apyPct': float(r['projected_supply_apy_pct'])}
                                       for r in observation['markets']}, 'capitalUsd': capital, 'maxPerPoolPct': 60})
        boundary = 'Only current Venus Core USDT/USDC rates are read. Budget and the 60% concentration cap are your assumptions. Capacity and independent risk scores are unavailable; TVL is not provided and provider default risk scores are not verified facts. Migration fees, exit limits, rewards and depeg risk are excluded.'
    return {'task_input': task, 'observation': observation, 'boundary': boundary,
            'scope': 'point_in_time_calculation', 'paid': False, 'trade_executed': False}
