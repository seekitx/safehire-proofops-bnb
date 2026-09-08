from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from test_routes import create_app

from proofops.arena import external_reports


@pytest.mark.anyio
@pytest.mark.parametrize('mutation', ['valid', 'wrong_position', 'stale', 'oversize', 'http_error'])
async def test_external_report_preserves_bytes_and_rejects_invalid_delivery(monkeypatch, mutation):
    measured = datetime.now(UTC) - timedelta(seconds=600 if mutation == 'stale' else 1)
    value = {'service': 'lp_position_look', 'position': '12' if mutation == 'wrong_position' else '7319347',
             'positions': 1, 'in_range': True, 'pool': {}, 'measured_at': measured.isoformat(),
             'verdict': 'Supplier text, not a signature'}
    raw = json.dumps(value, indent=3).encode()
    if mutation == 'oversize':
        raw += b' ' * 65000
    def reply(request):
        assert request.url.host == 'agent.brainonbnb.com'
        assert request.url.params['position'] == '7319347'
        return httpx.Response(503 if mutation == 'http_error' else 200, content=raw)
    client = httpx.AsyncClient(transport=httpx.MockTransport(reply))
    monkeypatch.setattr(external_reports.httpx, 'AsyncClient', lambda **kwargs: client)
    if mutation != 'valid':
        with pytest.raises((ValueError, httpx.HTTPError)):
            await external_reports.read_lp_report(7319347)
    else:
        result = await external_reports.read_lp_report(7319347)
        assert result['raw_text'].encode() == raw
        assert result['raw_sha256'] == hashlib.sha256(raw).hexdigest()
        assert result['payment_verified'] is False
        assert result['verification']['financial_accuracy_verified'] is False


def test_external_report_requires_explicit_consent_and_deployment(tmp_path):
    with TestClient(create_app(tmp_path)) as client:
        assert client.post('/api/arena/external-reports/lp', json={
            'position_id': 7319347, 'consent_send_position': False}).status_code == 422
    with TestClient(create_app(tmp_path, enabled=False)) as client:
        assert client.post('/api/arena/external-reports/lp', json={
            'position_id': 7319347, 'consent_send_position': True}).status_code == 503
