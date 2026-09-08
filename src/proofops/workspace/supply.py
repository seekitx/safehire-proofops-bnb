"""Probes fixed reviewed suppliers with public sample tasks. Never funds or notifies jobs."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx

from proofops.services.live_agent_market import (
    _load_catalog,
    new_hire_pause,
    request_live_agent_quote,
)
from proofops.workspace.store import Journal


def status(value: dict[str, Any] | None, *, now: float | None = None) -> dict[str, Any]:
    now = time.time() if now is None else now
    if not value:
        return {'state':'unchecked','can_request_quote':False}
    result = dict(value)
    if now - result['checked_at'] > 360 or (result['state']=='quote_verified' and result.get('expires_at',0) <= now):
        result['state']='stale'
    result['can_request_quote']=result['state']=='quote_verified'
    return result


def failure_details(exc: Exception) -> dict[str, str]:
    message=str(exc).lower()
    if isinstance(exc,(TimeoutError,httpx.TimeoutException)):
        code,reason='timeout','The provider did not respond before the deadline.'
    elif isinstance(exc,httpx.HTTPStatusError):
        code,reason='http_'+str(exc.response.status_code),'Provider endpoint unavailable. HTTP '+str(exc.response.status_code)
    elif 'complete signed' in message:
        code,reason='signed_envelope_missing','The provider returned no complete signed quote. An unsigned quote cannot authorize payment.'
    elif 'expir' in message:
        code,reason='quote_expired','The quote has expired. The provider must issue a new one.'
    elif any(s in message for s in ['wallet','signer','signature','provider']):
        code,reason='identity_or_signature_mismatch','Provider identity or signature verification failed.'
    elif any(s in message for s in ['price','currency','token','chain','contract']):
        code,reason='commercial_terms_mismatch','Price, currency, chain or contracts differ from the reviewed scope.'
    else:
        code,reason='response_contract_mismatch','The response does not match the integration contract. Payment is unavailable.'
    return {'code':code,'reason':reason,'action':'Repair or revalidate the integration. Signature checks cannot be bypassed.'}


async def probe(root: Path, journal: Journal) -> None:
    agents=sorted(_load_catalog(root)['agents'],key=lambda a:not bool(a.get('verified_submitted_job_ids')))
    for agent in agents:
        token = agent['token_id']
        started = time.time()
        value: dict[str, Any] = {'checked_at':started, 'sample_task_only':True, 'paid_delivery_proved':False}
        pause = new_hire_pause(root, token)
        if pause:
            value.update(state='paused', reason=pause)
        else:
            try:
                async with asyncio.timeout(30):
                    quote=await request_live_agent_quote(root,skill_id=agent['skill_id'],agent_token_id=token)
                value.update(state='quote_verified', price_raw=quote['quote']['price'],
                             price_display=quote['quote']['price_display'],
                             expires_at=quote['quote_verification']['quote_expires_at'],
                             provider=quote['quote_verification']['provider'])
            except (ValueError, TypeError, KeyError, TimeoutError, httpx.HTTPError) as exc:
                # Capability probe failures must not kill the independent order worker.
                value.update(state='unavailable', failure=failure_details(exc), reason=failure_details(exc)['reason'])
        value['duration_seconds']=round(time.time()-started,3)
        journal.save_provider_probe(token,value)


async def run(root: Path, journal: Journal) -> None:
    while True:
        started=time.time()
        try:
            await probe(root,journal)
        except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
            logging.getLogger(__name__).warning('Supplier probe unavailable: %s', type(exc).__name__)
            # Persisted probe times are never refreshed on failure and expire in projection.
        await asyncio.sleep(max(30,300-(time.time()-started)))
