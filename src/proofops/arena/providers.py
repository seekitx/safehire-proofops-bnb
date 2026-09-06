"""Config-reviewed, quote-only provider federation; no arbitrary public URLs.

Manifest review is operator configuration, NOT proof of onchain identity or an
independent business. A new settlement adapter must be separately reviewed.
"""
from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import Field, StrictInt, model_validator

from proofops.arena.models import Category, StrictModel, TaskSpec, utcnow

REGISTRY = '0x8004a169fb4a3325136eb29fa0ceb6d2e539a432'


class ProviderSpec(StrictModel):
    provider_id: str = Field(pattern=r'^[a-z0-9_-]{1,64}$')
    operator_label: str = Field(min_length=1, max_length=120)
    token_id: StrictInt = Field(gt=0, lt=2**256)
    chain_id: Literal[56] = 56
    registry: str = REGISTRY
    skill_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    category: Category
    endpoint: str = Field(max_length=300)
    protocol: Literal['brain-a2a-v1', 'safehire-quote-v2']
    reviewed_scope: str = Field(min_length=1, max_length=120)
    quote_enabled: bool = False

    @model_validator(mode='after')
    def safe_manifest(self) -> ProviderSpec:
        url = urlsplit(self.endpoint)
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.fragment or url.query or url.port not in (None, 443):
            raise ValueError('provider requires an HTTPS URL without credentials/query/fragment or nonstandard port')
        host = url.hostname.lower()
        if '.' not in host or host.endswith(('.local', '.localhost', '.internal')) or host == 'localhost':
            raise ValueError('provider hostname must be public')
        try:
            ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            raise ValueError('literal IP endpoints are not allowed')
        if self.registry.lower() != REGISTRY:
            raise ValueError('unreviewed identity registry')
        if self.protocol == 'brain-a2a-v1' and self.endpoint != 'https://agent.brainonbnb.com/a2a':
            raise ValueError('Brain adapter is pinned to its reviewed endpoint')
        return self

    @property
    def agent_ref(self) -> str:
        return f'56:{self.token_id}:{self.skill_id}'


class ProviderCatalog:
    def __init__(self, providers: list[ProviderSpec]) -> None:
        if len(providers) > 100:
            raise ValueError('provider catalog maximum is 100 skill routes')
        if len({p.agent_ref for p in providers}) != len(providers):
            raise ValueError('duplicate registry identity + skill route')
        self.providers = tuple(providers)

    @classmethod
    def load(cls, path: Path) -> ProviderCatalog:
        if path.stat().st_size > 100000:
            raise ValueError('provider manifest exceeds 100 KiB')
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict) or set(raw) != {'schema_version', 'providers'} or raw['schema_version'] != 'safehire-providers/2':
            raise ValueError('unexpected provider manifest schema')
        return cls([ProviderSpec.model_validate(row) for row in raw['providers']])

    def select(self, agent_ref: str, category: str) -> ProviderSpec:
        found = next((p for p in self.providers if p.agent_ref == agent_ref and p.category == category), None)
        if found is None:
            raise ValueError('identity/skill/category route is not in the reviewed manifest')
        return found

    def public(self) -> dict[str, Any]:
        return {'schema_version': 'safehire-provider-view/2', 'providers': [
            {**p.model_dump(), 'agent_ref': p.agent_ref, 'live_verified': False,
             'business_independence_verified': False, 'settlement_enabled': False}
            for p in self.providers],
            'declared_operator_count': len({p.provider_id for p in self.providers}),
            'identity_review': 'server_manifest_only_not_current_chain_verification',
            'live_execution_or_quality_proven': False}


async def public_dns(host: str) -> None:
    loop = asyncio.get_running_loop()
    addresses = await asyncio.wait_for(loop.getaddrinfo(host, 443, type=socket.SOCK_STREAM), 3)
    if not addresses or any(not ipaddress.ip_address(row[4][0]).is_global for row in addresses):
        raise ValueError('provider resolves to a non-public address')
    # DNS rebinding between this check and connect requires deployment egress ACLs.


class QuoteGateway:
    def __init__(self, catalog: ProviderCatalog, *, transport: httpx.AsyncBaseTransport | None = None,
                 dns_check: Callable[[str], Awaitable[None]] = public_dns,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.catalog, self.transport, self.dns_check, self.clock = catalog, transport, dns_check, clock
        self.failures: dict[str, tuple[int, float]] = {}
        self.semaphore = asyncio.Semaphore(4)

    async def quote(self, task: TaskSpec, agent_ref: str) -> dict[str, Any]:
        provider = self.catalog.select(agent_ref, task.category)
        if not provider.quote_enabled:
            raise ValueError('provider quote route is disabled until operator review')
        if not task.fresh():
            raise ValueError('snapshot expired; obtain a new source snapshot')
        failures, until = self.failures.get(agent_ref, (0, 0))
        if failures >= 3 and self.clock() < until:
            raise ValueError('provider circuit open after repeated failures; no fallback supplier used')
        if self.clock() >= until:
            failures = 0
        try:
            async with asyncio.timeout(20):
                async with self.semaphore:
                    result = await self._call(provider, task)
            self.failures.pop(agent_ref, None)
            return result
        except (httpx.HTTPError, OSError, ValueError, TypeError, KeyError, TimeoutError, OverflowError, RecursionError):
            self.failures[agent_ref] = (failures + 1, self.clock() + 30)
            raise

    async def _call(self, provider: ProviderSpec, task: TaskSpec) -> dict[str, Any]:
        await self.dns_check(urlsplit(provider.endpoint).hostname or '')
        if provider.protocol == 'brain-a2a-v1':
            payload = {'jsonrpc': '2.0', 'id': task.task_hash, 'method': 'message/send', 'params': {
                'message': {'role': 'user', 'messageId': task.task_hash, 'parts': [{'kind': 'data', 'data': {
                    'skill': 'negotiate', 'service': provider.skill_id,
                    'task_description': f'Read-only {task.category} analysis; do not sign, trade or move funds. Task {task.task_hash}',
                    'terms': {'deliverables': provider.reviewed_scope,
                              'quality_standards': 'Name sources and timestamps; disclose uncertainty; no profit guarantees.'}}}]}}}
        else:
            payload = {'schema_version': 'safehire-quote-request/2', 'task_hash': task.task_hash,
                       'agent_ref': provider.agent_ref, 'task': task.to_dict(), 'requested_action': 'quote_only'}
        started = self.clock()
        async with (
            httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False, transport=self.transport) as client,
            client.stream('POST', provider.endpoint, json=payload) as response,
        ):
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError('only a successful 200 quote response is supported')
            chunks, size = [], 0
            async for chunk in response.aiter_bytes():
                size += len(chunk)
                if size > 64000:
                    raise ValueError('quote response exceeds 64 KiB')
                chunks.append(chunk)
        raw = b''.join(chunks)
        body = json.loads(raw)
        if not isinstance(body, dict):
            raise TypeError('quote must be a JSON object')
        task_bound = provider.protocol == 'safehire-quote-v2'
        q = body if task_bound else body.get('result')
        if not isinstance(q, dict) or q.get('accepted') is not True or body.get('error'):
            raise ValueError('provider did not accept quote request')
        if type(q.get('chain_id')) is not int or q['chain_id'] != 56:
            raise ValueError('quote chain is not BSC mainnet')
        if task_bound:
            if q.get('task_hash') != task.task_hash or q.get('agent_ref') != provider.agent_ref:
                raise ValueError('quote does not bind requested task/identity/skill')
        elif q.get('service') != provider.skill_id:
            raise ValueError('quote skill mismatch')
        price = q.get('price_raw', q.get('price'))
        if type(price) not in (int, str) or not str(price).isascii() or not str(price).isdigit() or not 0 <= int(price) < 2**256:
            raise ValueError('quote price must be an unsigned raw integer amount')
        payment_token = q.get('payment_token')
        if payment_token is not None and (not isinstance(payment_token, str) or not re.fullmatch(r'0x[0-9a-fA-F]{40}', payment_token)):
            raise ValueError('quote payment token must be an EVM address, not a ticker')
        deadline = q.get('expires_at')
        # Unknown expiry is explicitly unusable, not an invented fresh quote.
        expires = None
        if deadline is not None:
            if type(deadline) is int:
                expires = datetime.fromtimestamp(deadline, UTC)
            elif isinstance(deadline, str):
                expires = datetime.fromisoformat(deadline)
            if expires is None or expires.tzinfo is None or expires <= utcnow():
                raise ValueError('quote expired or expiry is invalid')
        return {'schema_version': 'safehire-observed-quote/2', 'agent_ref': provider.agent_ref,
                'provider_id': provider.provider_id, 'observed_at': utcnow().isoformat(),
                'latency_ms': round((self.clock() - started) * 1000, 3),
                'raw_response_sha256': hashlib.sha256(raw).hexdigest(),
                'task_hash': task.task_hash, 'provider_echoed_task_binding': task_bound,
                'signature_verified': False, 'identity_currently_verified': False,
                'price_raw': str(price), 'payment_token': payment_token,
                'expires_at': expires.isoformat() if expires else None,
                'quote_status': 'unsigned_task_bound_quote' if task_bound and expires else 'informational_only',
                'evidence_mode': 'observed_provider_response_not_payment_proof',
                'settlement_enabled': False, 'trade_executed': False,
                'scope': 'quote_only_no_delivery_requested'}
