from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from proofops.arena.examples import examples
from proofops.arena.lp_sources import observe_lp, source_lp_task
from proofops.arena.models import TaskSpec, utcnow
from proofops.arena.store import TaskStore
from proofops.decision.paid import BscReader

SAMPLE = Path(__file__).resolve().parents[2] / 'evidence/marketplace/lp-position-observation-2026-09-08.json'


class ReplayReader(BscReader):
    chain = '0x38'
    reorg = False
    stale = False
    corrupt = False

    def __init__(self):
        self.sample = json.loads(SAMPLE.read_text())

    async def rpc(self, method, params):
        s = self.sample
        if method == 'eth_chainId':
            return self.chain
        if method == 'eth_blockNumber':
            return hex(s['block_number'] + 12)
        if method == 'eth_getBlockByNumber':
            return {'number': hex(s['block_number']), 'hash': s['block_hash'],
                    'timestamp': hex(int(utcnow().timestamp()) - (500 if self.stale else 0))}
        assert method == 'eth_call'
        assert params[1] == {'blockHash': s['block_hash'], 'requireCanonical': True}
        row = next(row for row in s['raw_reads'] if row['to'] == params[0]['to'] and row['calldata'] == params[0]['data'])
        return row['result'] + ('00' if self.corrupt else '')

    async def canonical_block_hash(self, block_number):
        return '0x' + '0' * 64 if self.reorg else self.sample['block_hash']


def test_real_bytes_replay_preserves_position_and_explicit_assumptions(tmp_path):
    observation = asyncio.run(observe_lp(7319347, reader=ReplayReader()))
    original = TaskSpec.model_validate(examples()['tasks']['rebalancing'])
    task = source_lp_task(original, observation)
    assert task.inputs['liquidity_raw'] == int(observation['liquidity_raw'])
    assert task.inputs['estimated_cost_usd'] == original.inputs['estimated_cost_usd']
    assert task.snapshot.block_hash == observation['block_hash']
    assert not observation['ownership_by_caller_verified']
    assert not observation['settlement_authorized']
    store = TaskStore(tmp_path / 'lp.sqlite3')
    opened = store.create(task, source_observation=observation)
    bundle = store.bundle(opened['task_id'], opened['task_token'])
    assert bundle['task']['inputs']['current_tick'] == observation['current_tick']


@pytest.mark.parametrize('field,value', [('chain', '0x61'), ('reorg', True), ('stale', True), ('corrupt', True)])
def test_rejects_invalid_chain_stale_reorganized_or_malformed_data(field, value):
    reader = ReplayReader()
    setattr(reader, field, value)
    with pytest.raises(ValueError):
        asyncio.run(observe_lp(7319347, reader=reader))


@pytest.mark.parametrize('position', [True, 0, -1, 2**53])
def test_invalid_position_rejected_before_network(position):
    with pytest.raises(ValueError):
        asyncio.run(observe_lp(position, reader=ReplayReader()))
