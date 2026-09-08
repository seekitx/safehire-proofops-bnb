from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from eth_abi import encode

from proofops.arena import health_sources
from proofops.decision.paid import BscReader

SAMPLE = Path(__file__).resolve().parents[2] / 'evidence/marketplace/venus-health-observation-2026-09-08.json'


class Replay(BscReader):
    def __init__(self, mode='valid'):
        self.sample = json.loads(SAMPLE.read_text())
        self.mode = mode

    async def rpc(self, method, params):
        s = self.sample
        if method == 'eth_chainId':
            return '0x61' if self.mode == 'wrong_chain' else '0x38'
        if method == 'eth_blockNumber':
            return hex(s['block_number'] + 12)
        if method == 'eth_getBlockByNumber':
            return {'number': hex(s['block_number']), 'hash': s['block_hash'], 'timestamp': hex(s['block_timestamp'])}
        assert method == 'eth_call'
        assert params[1] == {'blockHash': s['block_hash'], 'requireCanonical': True}
        row = next(row for row in s['raw_reads'] if row['to'] == params[0]['to'] and row['calldata'] == params[0]['data'])
        if self.mode == 'emode' and row['function'] == 'userPoolId(address)':
            return '0x' + encode(['uint96'], [1]).hex()
        if self.mode == 'vai' and row['function'] == 'mintedVAIs(address)':
            return '0x' + encode(['uint256'], [1]).hex()
        if self.mode == 'wrong_total' and row['function'] == 'getAccountLiquidity(address)':
            return '0x' + encode(['uint256'] * 3, [0, 1, 0]).hex()
        return row['result']

    async def canonical_block_hash(self, block_number):
        return '0x'+'0'*64 if self.mode == 'reorg' else self.sample['block_hash']


@pytest.mark.anyio
@pytest.mark.parametrize('mode', ['valid', 'wrong_chain', 'emode', 'vai', 'wrong_total', 'reorg', 'stale'])
async def test_same_block_real_venus_replay_and_failure_boundaries(monkeypatch, mode):
    reader = Replay(mode)
    at = reader.sample['block_timestamp'] + (600 if mode == 'stale' else 6)
    monkeypatch.setattr(health_sources, 'utcnow', lambda: datetime.fromtimestamp(at, UTC))
    if mode != 'valid':
        with pytest.raises(ValueError):
            await health_sources.observe_health(reader.sample['account'], reader=reader)
    else:
        result = await health_sources.observe_health(reader.sample['account'], reader=reader)
        assert result['health_factor'] == reader.sample['health_factor']
        assert result['debt_usd'] == reader.sample['debt_usd']
        assert result['trade_executed'] is False
        assert result['block_hash'] == reader.sample['block_hash']
