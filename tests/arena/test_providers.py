"""Read-only transport tests. Mock providers are NOT shipped as live marketplace supply."""
from __future__ import annotations

import asyncio
import json
from datetime import timedelta

import httpx
import pytest

from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec, utcnow
from proofops.arena.providers import ProviderCatalog, ProviderSpec, QuoteGateway, public_dns


def task():
    return TaskSpec.model_validate(examples()['tasks']['grid_trading'])


def provider(**changes):
    payload = {'provider_id': 'synthetic-test-only', 'operator_label': 'TEST ONLY', 'token_id': 123,
               'skill_id': 'grid_test', 'category': 'grid_trading', 'endpoint': 'https://example.org/quote',
               'protocol': 'safehire-quote-v2', 'reviewed_scope': 'synthetic grid proposal', 'quote_enabled': True}
    return ProviderSpec(**(payload | changes))


async def test_dns(_host):
    return None

test_dns.__test__ = False


def response(t, p, **changes):
    return {'accepted': True, 'chain_id': 56, 'task_hash': t.task_hash, 'agent_ref': p.agent_ref,
            'price_raw': '100', 'payment_token': '0x' + 'a'*40,
            'expires_at': (utcnow()+timedelta(minutes=2)).isoformat()} | changes


def invoke(t, p, body=None, *, status=200, dns=test_dns):
    recorded = []
    async def handler(request):
        recorded.append(json.loads(request.content))
        return httpx.Response(status, json=body if body is not None else response(t, p))
    gateway = QuoteGateway(ProviderCatalog([p]), transport=httpx.MockTransport(handler), dns_check=dns)
    return asyncio.run(gateway.quote(t, p.agent_ref)), recorded


@pytest.mark.parametrize('url', [
    'http://example.org/a', 'https://127.0.0.1/a', 'https://[::1]/a', 'https://localhost/a',
    'https://app.local/a', 'https://app.internal/a', 'https://user:pw@example.org/a',
    'https://example.org/a?target=evil', 'https://example.org/a#foo', 'https://example.org:444/a',
    'file:///etc/passwd', 'https://metadata/a',
])
def test_endpoint_manifest_rejects_unreviewed_network_shapes(url):
    with pytest.raises(ValueError):
        provider(endpoint=url)


def test_brain_adapter_endpoint_is_pinned():
    with pytest.raises(ValueError):
        provider(protocol='brain-a2a-v1')


def test_identity_skill_category_routing_and_no_independent_business_claim():
    p = provider()
    second_skill = provider(skill_id='another_skill')
    catalog = ProviderCatalog([p, second_skill])
    assert catalog.select(p.agent_ref, 'grid_trading') == p
    assert len(catalog.public()['providers']) == 2
    assert catalog.public()['declared_operator_count'] == 1
    assert all(not row['live_verified'] for row in catalog.public()['providers'])
    assert all(not row['business_independence_verified'] for row in catalog.public()['providers'])
    with pytest.raises(ValueError):
        ProviderCatalog([p, p])
    with pytest.raises(ValueError):
        catalog.select(p.agent_ref, 'rebalancing')
    with pytest.raises(ValueError):
        provider(chain_id=97)
    with pytest.raises(ValueError):
        provider(registry='0x'+'b'*40)


def test_quote_task_binding_and_no_settlement_or_signature_claim():
    t, p = task(), provider()
    result, sent = invoke(t, p)
    assert sent[0]['requested_action'] == 'quote_only'
    assert sent[0]['task_hash'] == t.task_hash
    assert sent[0]['task'] == t.to_dict()
    assert result['provider_echoed_task_binding']
    assert result['quote_status'] == 'unsigned_task_bound_quote'
    assert not result['settlement_enabled'] and not result['signature_verified']
    assert not result['identity_currently_verified'] and not result['trade_executed']


@pytest.mark.parametrize('changes', [
    {'chain_id': 97}, {'chain_id': True}, {'accepted': 'true'}, {'accepted': False},
    {'task_hash': 'f'*64}, {'agent_ref': '56:999:other'}, {'price_raw': -1},
    {'price_raw': True}, {'price_raw': '1.01'}, {'price_raw': str(2**256)},
    {'price_raw': '１００'}, {'expires_at': '2000-01-01T00:00:00Z'},
    {'expires_at': '2099-01-01T00:00:00'}, {'expires_at': 1.2},
    {'payment_token': 'USDT'}, {'payment_token': ['0x'+'a'*40]},
])
def test_malicious_or_mismatched_quote_rejected(changes):
    t, p = task(), provider()
    with pytest.raises((ValueError, TypeError, OverflowError)):
        invoke(t, p, response(t, p, **changes))


def test_unknown_quote_expiry_is_informational_not_fresh():
    t, p = task(), provider()
    result, _ = invoke(t, p, response(t, p, expires_at=None))
    assert result['quote_status'] == 'informational_only'
    assert result['expires_at'] is None


def test_legacy_brain_quote_cannot_claim_task_echo_binding():
    t = task()
    p = provider(protocol='brain-a2a-v1', endpoint='https://agent.brainonbnb.com/a2a', skill_id='grid_plan')
    body = {'jsonrpc': '2.0', 'id': t.task_hash,
            'result': {'accepted': True, 'chain_id': 56, 'service': 'grid_plan', 'price': '100'}}
    result, sent = invoke(t, p, body)
    assert sent[0]['params']['message']['parts'][0]['data']['skill'] == 'negotiate'
    assert not result['provider_echoed_task_binding']
    assert result['quote_status'] == 'informational_only'


@pytest.mark.parametrize('status', [301, 302, 307, 402, 429, 500])
def test_redirect_payment_required_and_errors_do_not_fallback_or_pay(status):
    with pytest.raises((httpx.HTTPError, ValueError)):
        invoke(task(), provider(), status=status)


def test_oversized_quote_rejected():
    t, p = task(), provider()
    with pytest.raises(ValueError, match='exceeds'):
        invoke(t, p, response(t, p, padding='a'*65000))


def test_disabled_route_or_expired_snapshot_no_network():
    async def handler(_request):
        raise AssertionError('network should never be invoked')
    p = provider(quote_enabled=False)
    gateway = QuoteGateway(ProviderCatalog([p]), transport=httpx.MockTransport(handler), dns_check=test_dns)
    with pytest.raises(ValueError, match='disabled'):
        asyncio.run(gateway.quote(task(), p.agent_ref))
    p = provider()
    stale = task(); stale.snapshot.observed_at -= timedelta(days=1)
    gateway = QuoteGateway(ProviderCatalog([p]), transport=httpx.MockTransport(handler), dns_check=test_dns)
    with pytest.raises(ValueError, match='expired'):
        asyncio.run(gateway.quote(stale, p.agent_ref))


def test_circuit_breaker_counts_three_failures_and_then_recovers():
    clock, calls = [10.0], []
    t, p = task(), provider()
    async def handler(request):
        calls.append(request)
        if len(calls) <= 3:
            return httpx.Response(503)
        return httpx.Response(200, json=response(t, p))
    gateway = QuoteGateway(ProviderCatalog([p]), transport=httpx.MockTransport(handler),
                           dns_check=test_dns, clock=lambda: clock[0])
    async def run():
        for _ in range(3):
            with pytest.raises(httpx.HTTPError):
                await gateway.quote(t, p.agent_ref)
        with pytest.raises(ValueError, match='circuit open'):
            await gateway.quote(t, p.agent_ref)
        assert len(calls) == 3
        clock[0] += 31
        result = await gateway.quote(t, p.agent_ref)
        assert result['provider_echoed_task_binding']
    asyncio.run(run())


def test_dns_check_denies_private_before_transport():
    async def deny(_host):
        raise ValueError('non-public address')
    with pytest.raises(ValueError, match='non-public'):
        invoke(task(), provider(), dns=deny)


def test_real_dns_policy_rejects_one_private_address_in_mixed_answer(monkeypatch):
    async def run():
        loop = asyncio.get_running_loop()
        async def resolution(*args, **kwargs):
            return [(2, 1, 6, '', ('8.8.8.8', 443)), (2, 1, 6, '', ('127.0.0.1', 443))]
        monkeypatch.setattr(loop, 'getaddrinfo', resolution)
        with pytest.raises(ValueError, match='non-public'):
            await public_dns('example.org')
    asyncio.run(run())


def test_catalog_schema_and_quota(tmp_path):
    path = tmp_path/'manifest.json'
    path.write_text(json.dumps({'schema_version': 'safehire-providers/2', 'providers': [provider().model_dump()]}))
    assert len(ProviderCatalog.load(path).providers) == 1
    path.write_text(json.dumps({'schema_version': 'bad', 'providers': []}))
    with pytest.raises(ValueError):
        ProviderCatalog.load(path)
    with pytest.raises(ValueError):
        ProviderCatalog([provider(token_id=i+1) for i in range(101)])
