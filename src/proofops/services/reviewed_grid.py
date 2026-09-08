"""Explicit ChainHelix adapter. Computation only; no order execution authority."""
from __future__ import annotations

import json
import math
from typing import Any

TOKEN_ID = 269224
WALLET = '0xb8143345687aa5a527f4f9568d508ebbc612d06d'
PRICE = 500_000_000_000_000_000


def inputs(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - {'price', 'budgetUsd', 'levels', 'spanPct', 'request_nonce'}:
        raise ValueError('Grid requires price, budgetUsd, levels and spanPct only')
    result: dict[str, Any] = {}
    for key, low, high, default in [('price', 0, 1e12, None), ('budgetUsd', 0, 1e9, None),
                                    ('spanPct', 0, 99, 2)]:
        value = raw.get(key, default)
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or not low < value <= high:
            raise ValueError(f'{key} must be a finite positive number, at most {high}')
        result[key] = value
    levels = raw.get('levels', 5)
    if type(levels) is not int or not 1 <= levels <= 50:
        raise ValueError('levels must be an integer from 1 to 50 per side')
    result['levels'] = levels
    if 'request_nonce' in raw:
        nonce = raw['request_nonce']
        if not isinstance(nonce, str) or not 16 <= len(nonce) <= 128 or not nonce.isascii():
            raise ValueError('Invalid grid request nonce')
        result['request_nonce'] = nonce
    return result


def acceptance(task: dict[str, Any], content: str) -> dict[str, Any]:
    """Never turn a provider's ok flag into a quality pass."""
    errors: list[str] = []
    checked = inputs(task)
    try:
        result = json.loads(content)
        def same(actual: Any, expected: float, label: str, tolerance: float = 1e-8) -> None:
            if type(actual) not in {int, float} or not math.isfinite(actual) or abs(actual-expected) > max(tolerance, abs(expected)*1e-10):
                errors.append(label)
        if not isinstance(result, dict) or result.get('ok') is not True or result.get('category') != 'grid':
            raise ValueError('Supplier returned an error or a different category')
        n = checked['levels']
        same(result.get('mark'), checked['price'], 'Wrong reference price')
        same(result.get('budgetUsd'), checked['budgetUsd'], 'Wrong budget')
        same(result.get('spanPct'), checked['spanPct'], 'Wrong range')
        same(result.get('levelsPerSide'), n, 'Wrong levels per side')
        size = checked['budgetUsd'] / (2*n)
        total = 0.0
        for key, direction in [('buys', -1), ('sells', 1)]:
            rows = result.get(key)
            if not isinstance(rows, list) or len(rows) != n:
                errors.append(f'{key}: expected {n} levels')
                continue
            for i, row in enumerate(rows, 1):
                if not isinstance(row, dict):
                    errors.append('Malformed level')
                    continue
                price = checked['price'] * (1 + direction * checked['spanPct']/100 * i/n)
                if row.get('side') != ('buy' if direction == -1 else 'sell'):
                    errors.append('Wrong order side')
                same(row.get('price'), price, f'{key} {i}: wrong price', 0.00000051)
                same(row.get('sizeUsd'), size, f'{key} {i}: wrong allocation', 0.00000051)
                same(row.get('amount'), size/price, f'{key} {i}: wrong quantity', 0.0000000051)
                total += size
        same(result.get('perLevelUsd'), size, 'Wrong per-level amount', 0.00000051)
        same(result.get('allocatedUsd'), checked['budgetUsd'], 'Wrong allocated total')
        same(total, checked['budgetUsd'], 'Incomplete allocation')
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        errors.append(str(exc))
    return {'schema': 'safehire-grid-acceptance/1', 'passed': not errors, 'failures': errors,
            'checks': ['task parameters', 'sides and level count', 'prices', 'sizes', 'quantities', 'total budget'],
            'human_quality_review': 'pending', 'trade_executed': False,
            'boundary': 'Arithmetic against signed caller inputs only. No live-price, fees, profit, order placement or stop-loss verification.'}
