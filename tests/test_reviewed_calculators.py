import asyncio
import json

import pytest

from proofops.services import reviewed_calculators as c
from proofops.services.live_erc8183 import PRICE_RAW, _parse_task_spec, _reviewed_price
from proofops.workspace import calculator_sources


@pytest.mark.parametrize('token', [269228, 269226])
def test_signed_task_recovery_is_bound_to_reviewed_wallet(token):
    task = c.inputs(token, c.sample(token))
    task['request_nonce'] = 'safehire-calculator-test-0001'
    description = {'version': 1, 'task': json.dumps(task)}
    wallet = c.SERVICES[token][1]
    recovered = _parse_task_spec(description, provider=wallet)
    assert recovered['erc8004_token_id'] == token
    assert recovered['service'] == c.SERVICES[token][0]
    assert recovered['task_input'] == task
    assert _reviewed_price(wallet) == c.PRICE
    with pytest.raises(ValueError):
        _parse_task_spec(description, provider='0x'+'a'*40)
    other = 269226 if token == 269228 else 269228
    with pytest.raises(ValueError):
        _parse_task_spec(description, provider=c.SERVICES[other][1])
    assert _reviewed_price('0x'+'a'*40) == PRICE_RAW


@pytest.mark.parametrize('token,key,value', [
    (269228, 'prices', {'ETH': 2000}), (269228, 'alertHF', True),
    (269228, 'criticalHF', 9), (269228, 'prices', {'ETH': float('inf'), 'USDT': 1}),
    (269226, 'capitalUsd', float('nan')), (269226, 'maxPerPoolPct', 101),
    (269226, 'pools', {'bad': {'apyPct': 2, 'riskScore': 6}}),
    (269226, 'pools', {'bad': {'apyPct': 2, 'execute': True}}),
])
def test_rejects_unsupported_or_ambiguous_inputs(token, key, value):
    task = c.sample(token); task[key] = value
    with pytest.raises(ValueError): c.inputs(token, task)


def test_health_source_conversion_preserves_weighted_health(monkeypatch):
    observation = {'markets': [
        {'supplied_usd': '2000', 'borrowed_usd': '500', 'liquidation_threshold': '0.8'},
        {'supplied_usd': '1000', 'borrowed_usd': '300', 'liquidation_threshold': '0.5'}]}
    async def read(account): return observation
    monkeypatch.setattr(calculator_sources, 'observe_health', read)
    result = asyncio.run(calculator_sources.prepare(269228, '0x'+'1'*40, 10000))
    task = result['task_input']
    weighted = sum(v['amount'] * v['liqThreshold'] * task['prices'][k] for k, v in task['collateral'].items())
    debt = sum(v * task['prices'][k] for k, v in task['debt'].items())
    assert weighted/debt == 2100/800
    assert result['observation'] == observation and not result['paid']
    observation['markets'] = []
    with pytest.raises(ValueError): asyncio.run(calculator_sources.prepare(269228, '0x'+'1'*40, 10000))


def test_yield_conversion_never_invents_capacity_or_risk_scores(monkeypatch):
    async def read(): return {'markets': [{'venue_id':'venus-core-usdt', 'projected_supply_apy_pct':'3.1234'}]}
    monkeypatch.setattr(calculator_sources, 'observe_venus', read)
    result = asyncio.run(calculator_sources.prepare(269226, None, 5000))
    assert result['task_input']['pools'] == {'venus-core-usdt': {'apyPct': 3.1234}}
    assert result['task_input']['capitalUsd'] == 5000
