from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from proofops.arena.delivery import accept_delivery
from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec, canonical, utcnow
from proofops.arena.planners import reference_proposal
from proofops.arena.providers import ProviderCatalog
from proofops.decision.paid import BscReader
from proofops.services.live_agent_market import _reviewed_request
from proofops.services.live_erc8183 import _parse_task_spec


def setup_delivery():
    task = TaskSpec.model_validate(examples()['tasks']['rebalancing'])
    catalog = ProviderCatalog.load(Path(__file__).resolve().parents[2] / 'config/arena-providers.json')
    provider = next(p for p in catalog.providers if p.category == task.category)
    proposal = reference_proposal(task).model_copy(update={'agent_ref': provider.agent_ref})
    delivery = {
        'chain_id': 56, 'job_id': 123, 'provider': '0x' + '1' * 40,
        'task_spec': {'erc8004_token_id': provider.token_id, 'service': provider.skill_id, 'arena_task': task.to_dict()},
        'verification': {**dict.fromkeys(('valid', 'hash_matches', 'job_matches', 'chain_matches', 'contracts_match'), True),
                         'content': canonical(proposal.model_dump(mode='json'))},
    }

    class Reader(BscReader):
        async def rpc(self, method, params):
            if method == 'eth_chainId':
                return '0x38'
            return {'hash': task.snapshot.block_hash, 'timestamp': hex(int(utcnow().timestamp()))}

        async def identity(self, token_id, block_hash):
            return {'wallet': '0x' + '1' * 40, 'owner': '0x' + '2' * 40}

        async def canonical_block_hash(self, block_number):
            return task.snapshot.block_hash

    async def loader(**kwargs):
        return delivery

    def run():
        return asyncio.run(accept_delivery(task, 123, provider.agent_ref, catalog, loader=loader, reader=Reader()))

    return delivery, run


def test_verified_delivery_preserves_financial_and_settlement_boundaries():
    _, run = setup_delivery()
    result = run()
    assert result['delivery_commitment_verified']
    assert result['snapshot_block_verified']
    assert not result['financial_inputs_authenticated']
    assert not result['payment_verified']
    assert not result['settlement_authorized']


def test_quote_and_anchored_description_keep_the_complete_task():
    task = TaskSpec.model_validate(examples()['tasks']['grid_trading'])
    request, _ = _reviewed_request(
        selected={'token_id': 302258}, skill_id='grid_plan',
        task_input={'token': '0x' + '1' * 40}, request_nonce='nonce-' + '1' * 20,
        arena_task=task.to_dict(),
    )
    parsed = _parse_task_spec({'version': 1, 'task': request['task_description']})
    assert TaskSpec.model_validate(parsed['arena_task']).task_hash == task.task_hash
    assert 'safehire-proposal/2' in request['terms']['success_criteria'][-1]


def test_old_delivery_without_signed_task_is_rejected():
    delivery, run = setup_delivery()
    del delivery['task_spec']['arena_task']
    with pytest.raises(ValueError):
        run()


def test_wrong_task_cannot_reuse_valid_delivery():
    delivery, run = setup_delivery()
    delivery['task_spec']['arena_task']['limits']['max_cost_usd'] += 1
    with pytest.raises(ValueError, match='Signed hire'):
        run()


def test_unverified_content_and_wrong_provider_are_rejected():
    delivery, run = setup_delivery()
    delivery['verification']['hash_matches'] = False
    with pytest.raises(ValueError, match='commitment'):
        run()
    delivery['verification']['hash_matches'] = True
    delivery['provider'] = '0x' + '3' * 40
    with pytest.raises(ValueError, match='Registry wallet'):
        run()


@pytest.mark.parametrize('category,skill', [
    ('rebalancing', 'rebalance_plan'), ('grid_trading', 'grid_plan'),
    ('yield_optimisation', 'yield_plan'), ('health_factor_monitoring', 'health_factor'),
])
def test_frozen_inputs_survive_signed_job_recovery(category, skill):
    from proofops.arena.examples import examples
    from proofops.integrations.erc8183_quote import canonical_json

    task = examples()['tasks'][category]
    spec = {'schema_version': 'safehire-external-hire-v2', 'service': skill,
            'erc8004_token_id': 42, 'request_nonce': 'safehire-bound-input-roundtrip',
            'task_input': task['inputs'], 'arena_task': task}
    parsed = _parse_task_spec({'version': 1, 'task': canonical_json(spec)})
    assert parsed['task_input'] == task['inputs']
    assert parsed['arena_task'] == task


def test_prepare_passes_frozen_inputs_to_quote_and_rejects_different_inputs(monkeypatch, tmp_path):
    import asyncio

    from proofops.arena.examples import examples
    from proofops.services import live_erc8183

    task = examples()['tasks']['yield_optimisation']
    called = []
    async def reject_quote(*args, **kwargs):
        called.append(kwargs)
        raise ValueError('test provider: no signature')
    monkeypatch.setattr(live_erc8183, 'request_live_agent_quote', reject_quote)
    kwargs = {'buyer': '0x' + '1' * 40, 'skill_id': 'yield_plan',
              'task_input': task['inputs'], 'arena_task': task}
    with pytest.raises(ValueError, match='test provider: no signature'):
        asyncio.run(live_erc8183.prepare_live_hire(tmp_path, **kwargs))
    assert called[0]['task_input'] == task['inputs']
    assert called[0]['arena_task'] == task
    kwargs['task_input'] = {**task['inputs'], 'capital_usd': 99999}
    with pytest.raises(ValueError, match='exactly match'):
        asyncio.run(live_erc8183.prepare_live_hire(tmp_path, **kwargs))
    assert len(called) == 1
