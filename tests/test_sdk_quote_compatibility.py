from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from proofops.integrations.erc8183_quote import (
    canonical_json,
    canonical_keccak,
    sdk_description_content,
    verify_negotiation_envelope,
)

# Real public signature, replayed at its recorded time for offline verification.
SAMPLE = Path(__file__).resolve().parents[1] / 'evidence/marketplace/lp-sdk-quote-2026-09-08.json'


async def verify(sample, *, chain='0x38'):
    envelope = sample['quote_envelope']
    async def rpc(method, params):
        if method == 'eth_chainId':
            return chain
        if method == 'eth_getBlockByNumber':
            return {'timestamp': hex(envelope['response']['negotiated_at'] + 1)}
        if method == 'eth_getCode':
            return '0x'
        raise AssertionError(method)
    return await verify_negotiation_envelope(
        envelope=envelope, expected_request=envelope['request'],
        provider=sample['quote']['provider'], expected_chain_id=56,
        expected_verifying_contract=sample['quote']['verifying_contract'],
        expected_payment_token=sample['quote']['payment_token'], expected_price_raw=10**17,
        rpc_url='unused-offline-test', rpc_call=rpc, quote_format='bnbagent-sdk-v1',
    )


@pytest.mark.anyio
async def test_real_sdk_signature_with_independently_recorded_format():
    sample = json.loads(SAMPLE.read_text())
    result = await verify(sample)
    assert result.provider.lower() == '0x20f1ca5d1e5a3ee94c29dbf95e6bf6cea6a8d64b'
    description = json.loads(result.job_description)
    assert description['task'] == sample['quote_envelope']['request']['task_description']
    assert 'evaluator_type' not in description['terms']


@pytest.mark.anyio
async def test_sdk_quote_rejects_wrong_rpc_chain():
    with pytest.raises(ValueError, match='chain numbers'):
        await verify(json.loads(SAMPLE.read_text()), chain='0x61')


@pytest.mark.anyio
async def test_sdk_timestamp_remains_signature_bound():
    sample = json.loads(SAMPLE.read_text())
    sample['quote_envelope']['response']['negotiated_at'] += 1
    with pytest.raises(ValueError, match='negotiation hash'):
        await verify(sample)


@pytest.mark.anyio
async def test_sdk_task_cannot_be_replaced_even_with_recomputed_request_hash():
    sample = json.loads(SAMPLE.read_text())
    envelope = sample['quote_envelope']
    task = json.loads(envelope['request']['task_description'])
    task['request_nonce'] = 'different-signed-job'
    envelope['request']['task_description'] = canonical_json(task)
    envelope['request_hash'] = canonical_keccak(envelope['request'])
    with pytest.raises(ValueError, match='negotiation hash'):
        await verify(sample)


def test_sdk_refuses_task_arrays_instead_of_sanitizing_them():
    sample = json.loads(SAMPLE.read_text())
    envelope = copy.deepcopy(sample['quote_envelope'])
    envelope['request']['task_description'] = '{"holdings":[]}'
    with pytest.raises(ValueError, match='sanitization'):
        sdk_description_content(envelope)


@pytest.mark.anyio
async def test_paid_description_survives_expiry_without_relaxing_new_quotes_or_signatures():
    from proofops.integrations.erc8183_quote import verify_job_description

    sample = json.loads(SAMPLE.read_text())
    verified = await verify(sample)
    description = json.loads(verified.job_description)

    async def rpc(method, params):
        if method == 'eth_chainId':
            return '0x38'
        if method == 'eth_getBlockByNumber':
            return {'timestamp': hex(description['quote_expires_at'] + 600)}
        if method == 'eth_getCode':
            return '0x'
        raise AssertionError(method)

    args = {'description': description, 'provider': sample['quote']['provider'],
                'expected_chain_id': 56,
                'expected_verifying_contract': sample['quote']['verifying_contract'],
                'expected_payment_token': sample['quote']['payment_token'],
                'expected_price_raw': 10**17, 'rpc_url': 'unused-offline-test', 'rpc_call': rpc}
    with pytest.raises(ValueError, match='not currently valid'):
        await verify_job_description(**args)
    result = await verify_job_description(**args, require_current_quote=False)
    assert result['valid'] is True
    description['task'] = '{}'
    with pytest.raises(ValueError, match='negotiation hash'):
        await verify_job_description(**args, require_current_quote=False)
