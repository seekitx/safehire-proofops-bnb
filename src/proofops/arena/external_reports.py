"""Read-only supplier report. Preserve exact bytes; never promote it to paid evidence."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from typing import Any

import httpx

ENDPOINT = 'https://agent.brainonbnb.com/lp/look'
MAX_BYTES = 64000


async def read_lp_report(position_id: int) -> dict[str, Any]:
    if isinstance(position_id, bool) or not 0 < position_id < 2**53:
        raise ValueError('Invalid position ID')
    started = time.monotonic()
    async with (
        httpx.AsyncClient(timeout=20, follow_redirects=False) as client,
        client.stream('GET', ENDPOINT, params={'position': str(position_id)}) as response,
    ):
        response.raise_for_status()
        raw = bytearray()
        async for chunk in response.aiter_bytes():
            raw.extend(chunk)
            if len(raw) > MAX_BYTES:
                raise ValueError('Supplier report exceeds size limit')
    text = bytes(raw).decode('utf-8')
    value = json.loads(text, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON')))
    if not isinstance(value, dict) or value.get('service') != 'lp_position_look':
        raise ValueError('Supplier returned an unexpected report')
    if str(value.get('position')) != str(position_id) or value.get('positions') != 1:
        raise ValueError('Supplier returned a different position')
    if not isinstance(value.get('in_range'), bool) or not isinstance(value.get('pool'), dict):
        raise TypeError('Supplier report is incomplete')
    measured = datetime.fromisoformat(str(value.get('measured_at', '')))
    if measured.tzinfo is None or not -30 <= (datetime.now(UTC) - measured).total_seconds() <= 300:
        raise ValueError('Supplier report timestamp is stale or invalid')
    return {
        'schema_version': 'safehire-external-report/1',
        'provider': 'Brain On BNB AI', 'source_url': f'{ENDPOINT}?position={position_id}',
        'requested_position_id': str(position_id), 'received_at': datetime.now(UTC).isoformat(),
        'elapsed_seconds': round(time.monotonic() - started, 3),
        'source_mode': 'external_readonly_unsigned', 'service_fee_raw': '0',
        'payment_verified': False, 'trade_executed': False, 'settlement_authorized': False,
        'raw_text': text, 'raw_sha256': hashlib.sha256(bytes(raw)).hexdigest(), 'report': value,
        'verification': {'position_matches': True, 'timestamp_recent': True,
                         'provider_signature_verified': False, 'financial_accuracy_verified': False},
        'boundary': 'Fetched directly from the named supplier over HTTPS. No payment, signature, execution or independent financial verification. Hash covers exact supplier bytes; it is not a supplier signature.',
    }
