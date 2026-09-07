from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from threading import Lock
from typing import Any, ParamSpec, TypeVar

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import Field, StrictBool, StrictInt
from starlette.concurrency import run_in_threadpool

from proofops.arena.examples import examples, walkthrough
from proofops.arena.models import StrictModel, TaskSpec
from proofops.arena.planners import compare, evaluate, reference_proposal
from proofops.arena.providers import ProviderCatalog, QuoteGateway
from proofops.arena.store import CapacityError, Conflict, MissingTask, TaskStore, parse_proposal

P = ParamSpec('P')
R = TypeVar('R')
Message = dict[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class Submission(StrictModel):
    proposal_text: str = Field(min_length=1, max_length=24000)
    expected_version: StrictInt = Field(ge=1)


class Comparison(StrictModel):
    proposal_ids: list[str] = Field(min_length=2, max_length=3)


class QuoteRequest(StrictModel):
    agent_ref: str = Field(min_length=1, max_length=180)
    consent_send_task: StrictBool


class DeliveryRequest(StrictModel):
    job_id: StrictInt = Field(gt=0, lt=2**256)
    agent_ref: str = Field(min_length=1, max_length=180)


class VenusTaskRequest(StrictModel):
    template: TaskSpec
    current_venue: str = Field(pattern=r'^venus-core-(usdt|usdc)$')
    account: str | None = Field(default=None, pattern=r'^0x[0-9a-fA-F]{40}$')
    consent_read_public_account: StrictBool


class WalletReadRequest(StrictModel):
    account: str = Field(pattern=r'^0x[0-9a-fA-F]{40}$')
    consent_read_public_account: StrictBool


def make_router(root: Path, *, store: TaskStore | None = None, gateway: QuoteGateway | None = None,
                enabled: bool | None = None) -> APIRouter:
    router = APIRouter(prefix='/api/arena', tags=['Task-bound acceptance arena'])
    active = enabled if enabled is not None else os.getenv('SAFEHIRE_ARENA_ENABLED', 'false').lower() == 'true'
    configured = ProviderCatalog.load(root / 'config/arena-providers.json')
    quote_gateway = gateway or QuoteGateway(configured)
    initialization = Lock()
    source_slots = asyncio.Semaphore(2)

    def storage() -> TaskStore:
        nonlocal store
        if not active:
            raise HTTPException(503, 'Private analysis storage disabled. Set SAFEHIRE_ARENA_ENABLED=true after deployment review.')
        with initialization:
            if store is None:
                store = TaskStore(Path(os.getenv('SAFEHIRE_ARENA_DB', str(root / '.data/arena.sqlite3'))))
        return store

    def token(authorization: str | None) -> str:
        if not authorization or not authorization.startswith('Bearer ') or not 32 <= len(authorization[7:]) <= 128:
            raise HTTPException(401, 'Bearer task capability required; never send wallet keys')
        return authorization[7:]

    def checked(fn: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return fn(*args, **kwargs)
        except MissingTask as exc:
            raise HTTPException(404, str(exc)) from exc
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except CapacityError as exc:
            raise HTTPException(429, str(exc)) from exc
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.get('/capabilities')
    def capabilities() -> dict[str, Any]:
        return {'task_storage_enabled': active, 'transaction_execution_enabled': False,
                'quotes_enabled': os.getenv('SAFEHIRE_PROVIDER_QUOTES_ENABLED', 'false').lower() == 'true',
                'default_task_quota': 2000, 'proposal_quota_per_task': 10,
                'source_truth': 'Default caller supplied. Venus source route records server-read rates; capital, costs and capacity remain assumptions.',
                'providers': configured.public()}

    @router.get('/examples')
    def sample_tasks() -> dict[str, Any]:
        return examples()

    @router.post('/sources/wallet')
    async def wallet_observation(request: WalletReadRequest) -> dict[str, Any]:
        from proofops.arena.wallet_sources import observe_wallet

        if not active:
            raise HTTPException(503, 'Arena sources disabled by deployment')
        if not request.consent_read_public_account:
            raise HTTPException(422, 'Explicit public account read consent required')
        if source_slots.locked():
            raise HTTPException(429, 'Source collector busy; retry later')
        try:
            async with source_slots:
                return await asyncio.wait_for(observe_wallet(request.account), timeout=60)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise HTTPException(422, 'Wallet snapshot rejected; no synthetic fallback') from exc
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise HTTPException(502, 'Wallet source unavailable; no transaction attempted') from exc

    @router.get('/synthetic-walkthrough/{category}')
    def synthetic_walkthrough(category: str) -> dict[str, Any]:
        return checked(walkthrough, category)

    @router.post('/preview')
    def preview(task: TaskSpec) -> dict[str, Any]:
        def build() -> dict[str, Any]:
            proposal = reference_proposal(task)
            return {'task_hash': task.task_hash, 'reference_proposal': proposal.model_dump(mode='json'),
                    'report': evaluate(task, proposal), 'source': 'local_reference_not_live_agent'}
        return checked(build)

    @router.post('/tasks', status_code=201)
    def create(task: TaskSpec) -> dict[str, Any]:
        return checked(storage().create, task)

    @router.post('/source-tasks/venus-yield', status_code=201)
    async def create_venus_task(request: VenusTaskRequest) -> dict[str, Any]:
        from proofops.arena.financial_sources import observe_venus, source_yield_task

        journal = storage()
        if not request.consent_read_public_account:
            raise HTTPException(422, 'Explicit consent to query public financial sources is required')
        if (request.template.category != 'yield_optimisation'
                or any(v['venue_id'] not in {'venus-core-usdt', 'venus-core-usdc'}
                       for v in request.template.inputs.get('venues', []))):
            raise HTTPException(422, 'Use a yield template with reviewed Venus venue IDs')
        if source_slots.locked():
            raise HTTPException(429, 'Financial source collector busy; retry later')
        try:
            async with source_slots:
                observation = await asyncio.wait_for(observe_venus(request.account), timeout=45)
            task = source_yield_task(request.template, observation, request.current_venue)
            result = await run_in_threadpool(checked, journal.create, task,
                                            source_observation=observation)
            return {**result, 'task': task.to_dict(), 'source_observation': observation,
                    'financial_inputs_authenticated': False,
                    'remaining_assumptions': ['capital_usd', 'migration_cost_usd', 'capacity_usd',
                                              'withdrawal_delay_days', 'horizon_days', 'limits'],
                    'account_is_current_venue_owner_verified': False}
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise HTTPException(422, 'Financial source rejected; no synthetic fallback') from exc
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise HTTPException(502, 'Financial source unavailable; no task or payment created') from exc

    @router.get('/tasks/{task_id}')
    def bundle(task_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        return checked(storage().bundle, task_id, token(authorization))

    @router.post('/tasks/{task_id}/proposals')
    def submit(task_id: str, request: Submission, authorization: str | None = Header(default=None),
               idempotency_key: str = Header(min_length=8, max_length=128)) -> dict[str, Any]:
        return checked(storage().submit, task_id, token(authorization), request.proposal_text,
                       request_key=idempotency_key, expected_version=request.expected_version)

    @router.post('/tasks/{task_id}/compare')
    def comparison(task_id: str, request: Comparison, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        data = checked(storage().bundle, task_id, token(authorization))
        rows = {p['proposal_id']: p for p in data['proposals']}
        if len(set(request.proposal_ids)) != len(request.proposal_ids) or any(p not in rows for p in request.proposal_ids):
            raise HTTPException(422, 'select two or three distinct stored proposals')
        return checked(compare, TaskSpec.model_validate(data['task']), [parse_proposal(rows[p]['raw_text']) for p in request.proposal_ids])

    @router.post('/tasks/{task_id}/quote')
    async def quote(task_id: str, request: QuoteRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        access = token(authorization)
        if not request.consent_send_task:
            raise HTTPException(422, 'Explicit consent to send the task to the configured provider is required')
        if os.getenv('SAFEHIRE_PROVIDER_QUOTES_ENABLED', 'false').lower() != 'true':
            raise HTTPException(503, 'Network quotes are disabled by deployment configuration')
        data = await run_in_threadpool(checked, storage().bundle, task_id, access)
        try:
            return await quote_gateway.quote(TaskSpec.model_validate(data['task']), request.agent_ref)
        except (ValueError, TypeError, OverflowError, RecursionError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except (OSError, TimeoutError) as exc:
            raise HTTPException(502, 'Provider unavailable; no payment or fallback was attempted') from exc
        except httpx.HTTPError as exc:
            raise HTTPException(502, 'Provider rejected the read-only quote request') from exc

    @router.post('/tasks/{task_id}/delivery-acceptance')
    async def delivery_acceptance(
        task_id: str, request: DeliveryRequest, authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        # Lazy import keeps the offline Arena usable without the chain extras.
        import asyncio

        from proofops.arena.delivery import accept_delivery

        data = await run_in_threadpool(checked, storage().bundle, task_id, token(authorization))
        try:
            return await asyncio.wait_for(accept_delivery(
                TaskSpec.model_validate(data['task']), request.job_id, request.agent_ref, configured,
            ), timeout=45)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except (httpx.HTTPError, OSError, TimeoutError) as exc:
            raise HTTPException(502, 'Delivery could not be verified; no settlement was attempted') from exc

    return router


class ArenaBoundaryMiddleware:
    """Bound body memory before JSON parsing and forbid caching private responses."""
    def __init__(self, app: Any, max_body_bytes: int = 64000) -> None:
        self.app, self.maximum = app, max_body_bytes

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' or not scope['path'].startswith('/api/arena'):
            await self.app(scope, receive, send)
            return
        messages, size = [], 0
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            size += len(message.get('body', b''))
            if size > self.maximum:
                await send({'type': 'http.response.start', 'status': 413,
                            'headers': [(b'content-type', b'application/json'), (b'cache-control', b'no-store')]})
                await send({'type': 'http.response.body', 'body': b'{"detail":"Arena request body exceeds 64 KiB"}'})
                return
            messages.append(message)
            if not message.get('more_body', False):
                break
        # Bound syntactic nesting before the framework JSON parser (strings ignored).
        depth, quoted, escaped = 0, False, False
        for byte in b''.join(m.get('body', b'') for m in messages):
            if quoted:
                if escaped:
                    escaped = False
                elif byte == 92:
                    escaped = True
                elif byte == 34:
                    quoted = False
            elif byte == 34:
                quoted = True
            elif byte in (91, 123):
                depth += 1
                if depth > 64:
                    await send({'type': 'http.response.start', 'status': 413,
                                'headers': [(b'content-type', b'application/json'), (b'cache-control', b'no-store')]})
                    await send({'type': 'http.response.body', 'body': b'{"detail":"Arena JSON nesting exceeds 64 levels"}'})
                    return
            elif byte in (93, 125):
                depth -= 1
        index = 0

        async def bounded_receive() -> dict[str, Any]:
            nonlocal index
            if index < len(messages):
                item = messages[index]
                index += 1
                return item
            return await receive()

        async def private_send(message: dict[str, Any]) -> None:
            if message['type'] == 'http.response.start':
                headers = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'cache-control']
                message['headers'] = headers + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]
            await send(message)
        await self.app(scope, bounded_receive, private_send)
