"""Real FastAPI routing with temporary storage; no production main lifespan or chain."""
from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec, canonical
from proofops.arena.planners import reference_proposal
from proofops.arena.routes import ArenaBoundaryMiddleware, make_router
from proofops.arena.store import TaskStore

ROOT = Path(__file__).resolve().parents[2]


def create_app(tmp_path, enabled=True, gateway=None):
    app = FastAPI()
    app.add_middleware(ArenaBoundaryMiddleware)
    app.include_router(make_router(ROOT, store=TaskStore(tmp_path/'arena.sqlite3'), enabled=enabled, gateway=gateway))
    return app


def task():
    return TaskSpec.model_validate(examples()['tasks']['grid_trading'])


def opened(client, spec):
    response = client.post('/api/arena/tasks', json=spec.to_dict())
    assert response.status_code == 201, response.text
    return response.json()


def submit(client, spec, created, *, version=1, key='request-001', ref=None):
    proposal = reference_proposal(spec)
    if ref:
        proposal.agent_ref = ref
    return client.post(f"/api/arena/tasks/{created['task_id']}/proposals",
                       headers={'Authorization': 'Bearer '+created['task_token'], 'Idempotency-Key': key},
                       json={'expected_version': version, 'proposal_text': canonical(proposal.model_dump())})


@pytest.mark.parametrize('category', list(examples()['tasks']))
def test_public_preview_has_four_equal_category_paths_and_no_funding(tmp_path, category):
    with TestClient(create_app(tmp_path, enabled=False)) as client:
        response = client.post('/api/arena/preview', json=examples()['tasks'][category])
        assert response.status_code == 200, response.text
        assert response.json()['report']['policy_accepted']
        assert response.headers['cache-control'] == 'no-store'
        assert not response.json()['report']['trade_executed']
        assert client.post('/api/arena/tasks', json=task().to_dict()).status_code == 503


def test_private_creation_save_idempotency_conflict_export_and_compare(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        spec = task(); created = opened(client, spec)
        a = submit(client, spec, created)
        assert a.status_code == 200
        retry = submit(client, spec, created)
        assert retry.json()['replayed']
        conflict = submit(client, spec, created, key='request-002')
        assert conflict.status_code == 409
        b = submit(client, spec, created, version=2, key='request-002', ref='local:comparison-test-only')
        assert b.status_code == 200
        url = '/api/arena/tasks/'+created['task_id']
        auth = {'Authorization': 'Bearer '+created['task_token']}
        bundle = client.get(url, headers=auth)
        assert bundle.status_code == 200 and bundle.json()['integrity']['valid']
        assert bundle.json()['version'] == 3
        assert bundle.headers['cache-control'] == 'no-store'
        assert created['task_token'] not in bundle.text
        comparison = client.post(url+'/compare', headers=auth,
                                 json={'proposal_ids': [a.json()['proposal_id'], b.json()['proposal_id']]})
        assert comparison.status_code == 200, comparison.text
        assert comparison.json()['winner'] is None
        assert len(comparison.json()['eligible_agent_refs']) == 2
        assert client.post(url+'/compare', headers=auth,
                           json={'proposal_ids': [a.json()['proposal_id'], a.json()['proposal_id']]}).status_code == 422


def test_capability_required_and_wrong_capability_does_not_enumerate(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        created = opened(client, task()); other = opened(client, task())
        url = '/api/arena/tasks/'+created['task_id']
        assert client.get(url).status_code == 401
        assert client.get(url, headers={'Authorization':'Bearer x'}).status_code == 401
        wrong = client.get(url, headers={'Authorization': 'Bearer '+other['task_token']})
        assert wrong.status_code == 404 and wrong.headers['cache-control'] == 'no-store'


def test_idempotency_header_required_and_body_extra_fields_rejected(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        spec = task(); created = opened(client, spec)
        response = client.post('/api/arena/tasks/'+created['task_id']+'/proposals',
                               headers={'Authorization': 'Bearer '+created['task_token']},
                               json={'expected_version': 1, 'proposal_text': canonical(reference_proposal(spec).model_dump())})
        assert response.status_code == 422
        bad = spec.to_dict() | {'paid_delivery_verified': True}
        assert client.post('/api/arena/preview', json=bad).status_code == 422


@pytest.mark.parametrize('size', [64001, 100000])
def test_oversized_body_rejected_before_json_parse(tmp_path, size):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post('/api/arena/preview', content='x'*size)
        assert response.status_code == 413
        assert response.headers['cache-control'] == 'no-store'


def test_chunked_request_is_bounded_even_without_content_length(tmp_path):
    async def run():
        async def chunks():
            for _ in range(5):
                yield b'x'*16000
        async with httpx.AsyncClient(transport=httpx.ASGITransport(create_app(tmp_path)), base_url='http://test') as client:
            response = await client.post('/api/arena/preview', content=chunks())
            assert response.status_code == 413
    asyncio.run(run())


def test_quote_requires_both_explicit_consent_and_deployment_flag(tmp_path, monkeypatch):
    monkeypatch.delenv('SAFEHIRE_PROVIDER_QUOTES_ENABLED', raising=False)
    with TestClient(create_app(tmp_path)) as client:
        created = opened(client, task()); url = '/api/arena/tasks/'+created['task_id']+'/quote'
        auth = {'Authorization': 'Bearer '+created['task_token']}
        assert client.post(url, headers=auth, json={'agent_ref':'56:302258:grid_plan','consent_send_task':False}).status_code == 422
        assert client.post(url, headers=auth, json={'agent_ref':'56:302258:grid_plan','consent_send_task':True}).status_code == 503
        monkeypatch.setenv('SAFEHIRE_PROVIDER_QUOTES_ENABLED', 'true')
        # Shipping manifest is disabled per route too: no real network request.
        assert client.post(url, headers=auth, json={'agent_ref':'56:302258:grid_plan','consent_send_task':True}).status_code == 422


def test_quote_transport_failure_gives_502_not_demo_success(tmp_path, monkeypatch):
    class Gateway:
        async def quote(self, *_args):
            raise httpx.ReadTimeout('synthetic timeout')
    monkeypatch.setenv('SAFEHIRE_PROVIDER_QUOTES_ENABLED', 'true')
    with TestClient(create_app(tmp_path, gateway=Gateway())) as client:
        created = opened(client, task())
        response = client.post('/api/arena/tasks/'+created['task_id']+'/quote',
                               headers={'Authorization':'Bearer '+created['task_token']},
                               json={'agent_ref':'56:302258:grid_plan', 'consent_send_task':True})
        assert response.status_code == 502
        assert 'settlement' not in response.json() and 'transaction_hash' not in response.json()


def test_deep_malformed_proposal_returns_validation_error_not_500(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        created = opened(client, task())
        response = client.post('/api/arena/tasks/'+created['task_id']+'/proposals',
                               headers={'Authorization':'Bearer '+created['task_token'], 'Idempotency-Key':'request-1'},
                               json={'proposal_text':'['*2000+']'*2000, 'expected_version':1})
        assert response.status_code == 422


def test_framework_json_depth_limited_and_consent_not_truthy_string(tmp_path, monkeypatch):
    with TestClient(create_app(tmp_path)) as client:
        response = client.post('/api/arena/preview', content='['*100+']'*100,
                               headers={'Content-Type':'application/json'})
        assert response.status_code == 413
        created = opened(client, task())
        url = '/api/arena/tasks/'+created['task_id']+'/quote'
        response = client.post(url, headers={'Authorization':'Bearer '+created['task_token']},
                               json={'agent_ref':'56:302258:grid_plan', 'consent_send_task':'true'})
        assert response.status_code == 422


def test_walkthrough_endpoint_default_readonly_and_unknown_category(tmp_path):
    with TestClient(create_app(tmp_path, enabled=False)) as client:
        for category in examples()['tasks']:
            response = client.get('/api/arena/synthetic-walkthrough/'+category)
            assert response.status_code == 200
            assert response.json()['real_provider_count'] == 0
        assert client.get('/api/arena/synthetic-walkthrough/unknown').status_code == 422
