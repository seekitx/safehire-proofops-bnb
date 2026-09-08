from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any, Literal

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

from proofops.services.live_agent_market import (
    _load_catalog,
    new_hire_pause,
    request_live_agent_quote,
)
from proofops.workspace.store import Journal


class WatchRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    kind: Literal['order', 'health', 'lp', 'grid', 'yield']
    job_id: StrictInt | None = Field(default=None, gt=0, lt=2**53)
    account: str | None = Field(default=None, pattern=r'^0x[0-9a-fA-F]{40}$')
    position_id: StrictInt | None = Field(default=None, gt=0, lt=2**53)
    threshold: float = Field(default=1.25, ge=1, le=10)
    target: float = Field(default=1.5, ge=1, le=10)
    lower: float = Field(default=700, gt=0, le=1e12)
    upper: float = Field(default=800, gt=0, le=1e12)
    capital: float = Field(default=10000, gt=0, le=1e9)
    days: StrictInt = Field(default=30, ge=1, le=365)
    cost: float = Field(default=1, ge=0, le=100000)
    minimum_gain: float = Field(default=1, ge=0, le=100000)
    current_venue: Literal['venus-core-usdt', 'venus-core-usdc'] = 'venus-core-usdt'
    notify_provider: StrictBool = False
    consent: StrictBool


class Feedback(BaseModel):
    model_config = ConfigDict(extra='forbid')
    useful: Literal['yes', 'partly', 'no', 'not_reviewed']
    comment: str = Field(max_length=1500)
    used_ai: StrictBool
    repurchase: Literal['yes', 'no', 'unknown'] = 'unknown'


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    price: float = Field(gt=0, le=1e12)
    budgetUsd: float = Field(gt=0, le=1e9)
    levels: StrictInt = Field(ge=1, le=50)
    spanPct: float = Field(gt=0, le=99)
    consent: StrictBool


class PushBinding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    device_key: str = Field(pattern=r'^[a-zA-Z0-9_-]{16,128}$')
    consent: StrictBool


class PushCode(BaseModel):
    model_config = ConfigDict(extra='forbid')
    code: str = Field(pattern=r'^\d{6}$')


class CalculatorSource(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    token_id: Literal[269228, 269226]
    account: str | None = Field(default=None, pattern=r'^0x[0-9a-fA-F]{40}$')
    capital: float = Field(default=10000, gt=0, le=1e9)
    consent: StrictBool


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    consent: StrictBool
    collateral_drop_pct: float = Field(default=20, ge=0, le=90)
    debt_rise_pct: float = Field(default=10, ge=0, le=200)
    half_width_ticks: StrictInt = Field(default=600, ge=1, le=100000)
    simulate_lp_exit: StrictBool = False
    slippage_bps: StrictInt = Field(default=50, ge=0, le=500)
    levels: StrictInt = Field(default=10, ge=2, le=50)
    capital: float = Field(default=1000, gt=0, le=1000000)
    gas_per_order: float = Field(default=0.2, ge=0, le=1000)
    transfer_tax_bps: StrictInt = Field(default=0, ge=0, le=1000)
    venue: Literal['venus-core-usdt','venus-core-usdc'] = 'venus-core-usdt'
    amount: str | None = Field(default=None, pattern=r'^\d{1,7}(?:\.\d{1,18})?$')


def make_router(root: Path, journal: Journal, *, enabled: bool | None = None) -> APIRouter:
    router = APIRouter(prefix='/api/workspace', tags=['Private orders and read-only monitoring'])
    active = enabled if enabled is not None else os.getenv('SAFEHIRE_FOLLOWUP_ENABLED', 'false').lower() == 'true'
    from proofops.workspace.notifications import Notifications
    notifications = Notifications(journal)
    quote_slots = asyncio.Semaphore(2)
    action_slots = asyncio.Semaphore(2)

    def auth(space: str, authorization: str | None) -> None:
        if not active:
            raise HTTPException(503, 'Server follow-up is not enabled')
        if not authorization or not authorization.startswith('Bearer ') or not 32 <= len(authorization[7:]) <= 128:
            raise HTTPException(401, 'Private workspace token required')
        try:
            journal.authorize(space, authorization[7:])
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get('/capabilities')
    def capabilities(request: Request) -> dict[str, Any]:
        task = getattr(request.app.state, 'followup_task', None)
        worker_running = task is not None and not task.done()
        return {'enabled': active, 'server_followup': active and worker_running, 'worker_running': worker_running, 'check_interval_seconds': 300,
                'monitor_duration_hours': 24, 'in_app_alerts': True,
                'external_push': bool(getattr(request.app.state, 'notification_task', None) and not request.app.state.notification_task.done()),
                'external_push_channel': 'bark', 'push_requires_verified_opt_in': True,
                'automatic_payment': False, 'automatic_trading': False, 'independent_review': False}

    @router.post('/spaces')
    def create() -> dict[str, str]:
        if not active:
            raise HTTPException(503, 'Server follow-up is not enabled')
        try:
            return journal.create_space()
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from exc

    @router.get('/spaces/{space}')
    def view(space: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        auth(space, authorization)
        return {'schema': 'safehire-service-journal/1', 'watches': journal.list(space),
                'boundary': 'Private local journal, not immutable evidence. Chain and source observations retain separate verification. In-app unread alerts do not prove human receipt.'}

    @router.get('/spaces/{space}/notifications')
    def notification_status(space: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        auth(space, authorization)
        return notifications.status(space)

    @router.post('/spaces/{space}/notifications/bind')
    async def notification_bind(space: str, body: PushBinding, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        auth(space, authorization)
        if not body.consent:
            raise HTTPException(422, 'First consent to storing the notification credential and sending a verification.')
        try:
            return await notifications.bind(space, body.device_key)
        except (ValueError, OSError) as exc:
            raise HTTPException(409, 'Unable to bind now. Wait one minute and retry, or check the server notification configuration.') from exc

    @router.post('/spaces/{space}/notifications/verify')
    def notification_verify(space: str, body: PushCode, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        auth(space, authorization)
        try:
            notifications.verify(space, body.code)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {'verified':True,'enabled':True,'evidence':'User returned the code sent to the device; not proof future alerts were read'}

    @router.post('/spaces/{space}/notifications/unsubscribe')
    def notification_unsubscribe(space: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
        auth(space, authorization)
        notifications.unsubscribe(space)
        return {'enabled':False,'destination_erased':True}

    @router.post('/spaces/{space}/watches')
    def add(space: str, body: WatchRequest, authorization: str | None = Header(default=None)) -> dict[str, str]:
        auth(space, authorization)
        if not body.consent:
            raise HTTPException(422, 'Consent to server storage and public-source reads is required')
        if body.kind == 'order' and body.job_id:
            spec: dict[str, Any] = {'job_id': body.job_id, 'notify_provider': body.notify_provider}
        elif body.kind == 'health' and body.account and int(body.account, 16):
            if body.target < body.threshold:
                raise HTTPException(422, 'Target must be at least the alert threshold')
            spec = {'account': body.account.lower(), 'threshold': body.threshold, 'target': body.target}
        elif body.kind == 'lp' and body.position_id:
            spec = {'position_id': body.position_id}
        elif body.kind == 'grid':
            if body.lower >= body.upper:
                raise HTTPException(422, 'Lower price must be below upper price')
            spec = {'lower':body.lower, 'upper':body.upper}
        elif body.kind == 'yield':
            spec = {k:getattr(body,k) for k in ('capital','days','cost','minimum_gain','current_venue')}
        else:
            raise HTTPException(422, 'Missing job, public account or LP position number')
        try:
            identifier = journal.add(space, body.kind, spec)
        except ValueError as exc:
            raise HTTPException(429, str(exc)) from exc
        return {'watch_id': identifier}

    @router.post('/spaces/{space}/watches/{watch}/pause')
    def pause(space: str, watch: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
        auth(space, authorization)
        try:
            journal.pause(space, watch)
        except LookupError as exc:
            raise HTTPException(404, str(exc)) from exc
        return {'paused': True}

    @router.post('/spaces/{space}/watches/{watch}/acknowledge')
    def acknowledge(space: str, watch: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
        auth(space, authorization)
        journal.acknowledge(space, watch)
        return {'acknowledged': True}

    @router.post('/spaces/{space}/watches/{watch}/feedback')
    def feedback(space: str, watch: str, body: Feedback, authorization: str | None = Header(default=None)) -> dict[str, bool]:
        auth(space, authorization)
        import json
        import time
        with journal.db() as db:
            if not db.execute('SELECT 1 FROM watches WHERE id=? AND space=?', (watch, space)).fetchone():
                raise HTTPException(404, 'Watch not found')
            if db.execute("SELECT count(*) FROM events WHERE watch=? AND kind='user_feedback'", (watch,)).fetchone()[0] >= 5:
                raise HTTPException(429, 'Feedback limit reached')
            db.execute('INSERT INTO events(watch,at,kind,data) VALUES(?,?,?,?)', (watch, time.time(), 'user_feedback', json.dumps(body.model_dump() | {'independent_review': False, 'wallet_ownership_verified': False})))
        return {'saved': True, 'independent_review': False}

    @router.post('/spaces/{space}/watches/{watch}/resume')
    def resume(space: str, watch: str, authorization: str | None = Header(default=None)) -> dict[str, bool]:
        auth(space, authorization)
        try:
            journal.resume(space,watch)
        except LookupError as exc:
            raise HTTPException(404,str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(409,str(exc)) from exc
        return {'resumed':True,'chain_deadline_changed':False}

    @router.post('/spaces/{space}/watches/{watch}/action-plan')
    async def action_plan(space: str, watch: str, body: ActionRequest, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        auth(space,authorization)
        if not body.consent:
            raise HTTPException(422,'Consent to public source reads and private plan storage required')
        if action_slots.locked():
            raise HTTPException(429,'Action preparation busy')
        from proofops.workspace.actions import prepare_action, token_amount
        try:
            row=journal.watch(space,watch)
            if body.amount is not None:
                token_amount(body.amount)
            if sum(e['kind']=='action_plan' for e in row['events']) >= 20:
                raise HTTPException(429,'Action preparation limit reached')
            async with action_slots:
                async with asyncio.timeout(65):
                    result=await prepare_action(row,body.model_dump(exclude={'consent'}))
            journal.save_action(space,watch,result)
            return result
        except LookupError as exc:
            raise HTTPException(404,str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(422,str(exc)) from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise HTTPException(503,'Live source or simulation unavailable; no action was sent') from exc

    @router.get('/services')
    def services() -> dict[str, Any]:
        from proofops.workspace.supply import status
        probes=journal.provider_probes()
        rows = []
        for a in _load_catalog(root)['agents']:
            rows.append({'token_id': a['token_id'], 'name': a['name'], 'category': a['category'],
                         'skill_id': a['skill_id'], 'operator': a.get('operator', a.get('provider', {}).get('operator', 'Brain On BNB AI')),
                         'description': a['description'], 'scope': a.get('scope', 'analysis_only'),
                         'pause': new_hire_pause(root, a['token_id']),
                         'availability': status(probes.get(a['token_id'])),
                         'quote_price_is_live': False, 'price_raw': a.get('price_raw'),
                         'submitted_evidence': a.get('verified_submitted_job_ids', []),
                         'completion_rate': None, 'sample_size_note': 'No success-rate estimate from a single order',
                         'hire_url': f"/hire-live?skill_id={a['skill_id']}&agent_token_id={a['token_id']}"})
        rows.sort(key=lambda r:(not r['availability']['can_request_quote'],not bool(r['submitted_evidence']),r['token_id']))
        return {'services': rows, 'evidence_boundary': 'Listings describe reviewed scope; a current valid quote is required before purchase. Operators are grouped, never counted as independent agents.'}

    @router.post('/calculator-source')
    async def calculator_source(body: CalculatorSource) -> dict[str, Any]:
        if not active:
            raise HTTPException(503, 'Live sources are not enabled')
        if not body.consent:
            raise HTTPException(422, 'First consent to reading public chain data.')
        if action_slots.locked():
            raise HTTPException(429, 'Data reads are busy. Try again shortly.')
        from proofops.workspace.calculator_sources import prepare
        try:
            async with action_slots:
                async with asyncio.timeout(55):
                    return await prepare(body.token_id, body.account, body.capital)
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        except (httpx.HTTPError, TimeoutError) as exc:
            raise HTTPException(503, 'Live data is unavailable. Retry; do not present assumptions as current observations.') from exc

    @router.post('/compare-grid')
    async def compare(body: CompareRequest) -> dict[str, Any]:
        if not body.consent:
            raise HTTPException(422, 'Consent required before sending task to supplier')
        if quote_slots.locked():
            raise HTTPException(429, 'Quote capacity busy; try again')
        rows: list[dict[str, Any]] = []
        async with quote_slots:
            for a in _load_catalog(root)['agents']:
                if a['category'] != 'grid_trading':
                    continue
                row = {'token_id': a['token_id'], 'name': a['name'], 'comparable': a['token_id'] == 269224}
                if a['token_id'] == 269224:
                    try:
                        quote = await request_live_agent_quote(root, skill_id='grid_plan', agent_token_id=269224,
                                                              task_input=body.model_dump(exclude={'consent'}))
                        row['quote'] = quote
                    except (httpx.HTTPError, ValueError, TypeError):
                        row['error'] = 'Current signed quote unavailable; do not fund'
                else:
                    row['reason'] = 'Uses pool/address inputs rather than this exact numeric grid task; not a like-for-like offer'
                rows.append(row)
        return {'same_task': body.model_dump(exclude={'consent'}), 'offers': rows, 'winner': None,
                'boundary': 'No automatic ranking, purchase or proof that two suppliers completed this task.'}

    return router
