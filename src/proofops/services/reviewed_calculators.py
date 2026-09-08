"""Two explicitly reviewed paid calculators; no execution or monitoring authority."""
from __future__ import annotations

import math
import re
from typing import Any

PRICE = 500_000_000_000_000_000
SERVICES = {
    269228: ('health_factor', '0x91f4602760e1627007bfc16f78a74cf8b9de8da2'),
    269226: ('yield_plan', '0xccae2da18278c663fc808fa858fd89cc34cf701f'),
}


def token_for_wallet(wallet: str) -> int | None:
    return next((token for token, (_, address) in SERVICES.items() if address == wallet.lower()), None)


def number(value: Any, low: float = 0, high: float = 1e12, *, positive: bool = False) -> float:
    if type(value) not in {int, float} or not math.isfinite(value) or not low <= value <= high or (positive and value == 0):
        raise ValueError('Calculator values must be finite numbers within the reviewed limits')
    return float(value)


def mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not 1 <= len(value) <= 16 or any(not isinstance(k, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', k) for k in value):
        raise ValueError('Supply 1–16 named assets or venues')
    return value


def inputs(token: int, raw: Any) -> dict[str, Any]:
    if token not in SERVICES or not isinstance(raw, dict):
        raise ValueError('Unsupported reviewed calculator')
    result: dict[str, Any]
    if token == 269228:
        if set(raw) - {'collateral', 'debt', 'prices', 'alertHF', 'criticalHF', 'request_nonce'}:
            raise ValueError('Only collateral, debt, prices and health thresholds are supported')
        collateral = {}
        for symbol, row in mapping(raw.get('collateral')).items():
            if not isinstance(row, dict) or set(row) != {'amount', 'liqThreshold'}:
                raise ValueError('Each collateral needs amount and liqThreshold')
            collateral[symbol] = {'amount': number(row['amount'], positive=True),
                                  'liqThreshold': number(row['liqThreshold'], high=1, positive=True)}
        debt = {k: number(v, positive=True) for k, v in mapping(raw.get('debt')).items()}
        prices = {k: number(v, positive=True) for k, v in mapping(raw.get('prices')).items()}
        if set(prices) != set(collateral) | set(debt):
            raise ValueError('Prices must cover exactly the supplied collateral and debt symbols')
        alert = number(raw.get('alertHF', 1.5), high=100, positive=True)
        critical = number(raw.get('criticalHF', 1.1), high=100, positive=True)
        if critical >= alert:
            raise ValueError('Critical health threshold must be below alert threshold')
        result = {'collateral': collateral, 'debt': debt, 'prices': prices, 'alertHF': alert, 'criticalHF': critical}
    else:
        if set(raw) - {'pools', 'capitalUsd', 'maxPerPoolPct', 'riskAversion', 'tvlCapPct', 'request_nonce'}:
            raise ValueError('Only pool rates, capital and allocation constraints are supported')
        pools = {}
        for name, row in mapping(raw.get('pools')).items():
            if not isinstance(row, dict) or 'apyPct' not in row or set(row) - {'apyPct', 'tvlUsd', 'riskScore'}:
                raise ValueError('Each pool needs apyPct and optional tvlUsd/riskScore')
            item = {'apyPct': number(row['apyPct'], high=1000)}
            if 'tvlUsd' in row:
                item['tvlUsd'] = number(row['tvlUsd'], positive=True)
            if 'riskScore' in row:
                item['riskScore'] = number(row['riskScore'], low=1, high=5)
            pools[name] = item
        result = {'pools': pools, 'capitalUsd': number(raw.get('capitalUsd'), high=1e9, positive=True),
                  'maxPerPoolPct': number(raw.get('maxPerPoolPct', 40), high=100, positive=True),
                  'riskAversion': number(raw.get('riskAversion', 0.5), high=1),
                  'tvlCapPct': number(raw.get('tvlCapPct', 5), high=100, positive=True)}
    if 'request_nonce' in raw:
        nonce = raw['request_nonce']
        if not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,128}', nonce):
            raise ValueError('Invalid calculator request nonce')
        result['request_nonce'] = nonce
    return result


def sample(token: int) -> dict[str, Any]:
    """Hypothetical examples for liveness only, never a real financial snapshot."""
    if token == 269228:
        return {'collateral': {'ETH': {'amount': 10, 'liqThreshold': 0.8}}, 'debt': {'USDT': 10000},
                'prices': {'ETH': 2000, 'USDT': 1}}
    if token == 269226:
        return {'pools': {'example_a': {'apyPct': 6.1}, 'example_b': {'apyPct': 4.2}},
                'capitalUsd': 10000, 'maxPerPoolPct': 60}
    raise ValueError('Unsupported calculator')
