from __future__ import annotations

import asyncio
import json
from copy import deepcopy

import pytest
from eth_abi.abi import encode
from eth_utils.crypto import keccak

from proofops.arena.examples import examples
from proofops.arena.financial_sources import (
    COMPTROLLER,
    MARKETS,
    UNDERLYINGS,
    annualized_supply_pct,
    observe_venus,
    source_yield_task,
)
from proofops.arena.models import TaskSpec, utcnow
from proofops.arena.store import TaskStore
from proofops.decision.paid import BscReader


class SourceReader(BscReader):
    chain = '0x38'
    reorg = False
    account_error = 0
    padding = bytes(64)

    async def rpc(self, method, params):
        if method == 'eth_chainId':
            return self.chain
        if method == 'eth_blockNumber':
            return hex(10012)
        if method == 'eth_getBlockByNumber':
            number = int(params[0], 16)
            return {'number': hex(number), 'hash': '0x' + 'a' * 64,
                    'timestamp': hex(int(utcnow().timestamp()) - (600 if number == 8800 else 0))}
        assert method == 'eth_call'
        assert params[1] == {'blockHash': '0x' + 'a' * 64, 'requireCanonical': True}
        underlying = next((UNDERLYINGS[k] for k, v in MARKETS.items() if v == params[0]['to']), '0x' + '1' * 40)
        rows = {
            'comptroller()': (['address'], [COMPTROLLER]),
            'underlying()': (['address'], [underlying]),
            'decimals()': (['uint8'], [18]),
            'supplyRatePerBlock()': (['uint256'], [400000000]),
            'accrualBlockNumber()': (['uint256'], [9900]),
            'getAccountSnapshot(address)': (['uint256'] * 4, [self.account_error, 100000000, 7, 2 * 10**26]),
        }
        for signature, (types, values) in rows.items():
            if params[0]['data'][2:10] == keccak(text=signature)[:4].hex():
                suffix = self.padding if signature in {'supplyRatePerBlock()', 'getAccountSnapshot(address)'} else b''
                return '0x' + (encode(types, values) + suffix).hex()
        raise AssertionError('Unexpected read')

    async def canonical_block_hash(self, block_number):
        return '0x' + ('b' if self.reorg else 'a') * 64


def test_source_collection_keeps_raw_values_and_limits():
    result = asyncio.run(observe_venus('0x' + '2' * 40, reader=SourceReader()))
    assert result['block_number'] == 10000
    assert result['markets'][0]['position']['supplied_underlying_stored_raw'] == '20000000000000000'
    assert result['raw_reads']
    assert not result['financial_inputs_authenticated']
    assert not result['markets'][0]['position']['fresh_interest_accrual_verified']


@pytest.mark.parametrize('field,value', [('chain', '0x61'), ('reorg', True), ('account_error', 1), ('padding', bytes(63) + b'\x01')])
def test_invalid_chain_reorg_and_protocol_error_fail_closed(field, value):
    reader = SourceReader()
    setattr(reader, field, value)
    with pytest.raises(ValueError):
        asyncio.run(observe_venus('0x' + '2' * 40, reader=reader))


def test_invalid_account_never_queries_rpc():
    with pytest.raises(ValueError, match='nonzero public'):
        asyncio.run(observe_venus('not-a-wallet', reader=SourceReader()))


def test_annualization_uses_observed_cadence():
    assert float(annualized_supply_pct(400000000, 600, 1200)) > float(annualized_supply_pct(400000000, 1200, 1200))
    assert annualized_supply_pct(0, 600, 1200) == '0E-8'
    with pytest.raises(ValueError):
        annualized_supply_pct(400000000, 0, 1200)


def test_server_source_task_replaces_rates_not_assumptions_and_exports_provenance(tmp_path):
    source = asyncio.run(observe_venus(reader=SourceReader()))
    raw = examples()['tasks']['yield_optimisation']
    for venue, venue_id in zip(raw['inputs']['venues'], MARKETS, strict=True):
        venue['venue_id'] = venue_id
    template = TaskSpec.model_validate(raw)
    original = deepcopy(template.to_dict())
    task = source_yield_task(template, source, 'venus-core-usdt')
    assert template.to_dict() == original
    assert task.inputs['current_apy_pct'] != template.inputs['current_apy_pct']
    assert task.inputs['capital_usd'] == template.inputs['capital_usd']
    assert task.inputs['venues'][0]['capacity_usd'] == template.inputs['venues'][0]['capacity_usd']
    store = TaskStore(tmp_path / 'arena.sqlite3')
    created = store.create(task, source_observation=source)
    bundle = store.bundle(created['task_id'], created['task_token'])
    assert bundle['integrity']['valid']
    event = json.loads(bundle['events'][0]['event_json'])
    assert event['kind'] == 'task_opened'
    assert event['data']['task_hash'] == task.task_hash
    assert event['data']['source_observation']['observation_hash'] == source['observation_hash']
    assert not event['data']['financial_inputs_authenticated']


def test_unknown_venue_cannot_borrow_source_provenance():
    source = asyncio.run(observe_venus(reader=SourceReader()))
    task = TaskSpec.model_validate(examples()['tasks']['yield_optimisation'])
    with pytest.raises(ValueError, match='Every venue'):
        source_yield_task(task, source, 'venus-core-usdt')
