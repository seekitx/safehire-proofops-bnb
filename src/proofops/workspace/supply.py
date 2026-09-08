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
                value.update(state='unavailable', reason=type(exc).__name__ + ': quote verification failed')
        value['duration_seconds']=round(time.time()-started,3)
        journal.save_provider_probe(token,value)


async def run(root: Path, journal: Journal) -> None:
    while True:
        try:
            await probe(root,journal)
        except (ValueError, TypeError, OSError, sqlite3.Error) as exc:
            logging.getLogger(__name__).warning('Supplier probe unavailable: %s', type(exc).__name__)
            # Persisted probe times are never refreshed on failure and expire in projection.
        await asyncio.sleep(300)
