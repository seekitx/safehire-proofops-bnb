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
        code,reason='timeout','供应商未在期限内响应'
    elif isinstance(exc,httpx.HTTPStatusError):
        code,reason='http_'+str(exc.response.status_code),'供应商接口暂不可用，HTTP '+str(exc.response.status_code)
    elif 'complete signed' in message:
        code,reason='signed_envelope_missing','供应商未返回完整签名报价，普通报价不能用于付款'
    elif 'expir' in message:
        code,reason='quote_expired','报价已过期，需要供应商重新签发'
    elif any(s in message for s in ['wallet','signer','signature','provider']):
        code,reason='identity_or_signature_mismatch','供应商身份或签名未通过核验'
    elif any(s in message for s in ['price','currency','token','chain','contract']):
        code,reason='commercial_terms_mismatch','费用、币种、链或合约与审核范围不一致'
    else:
        code,reason='response_contract_mismatch','返回内容不符合当前接入协议，暂不可付款'
    return {'code':code,'reason':reason,'action':'修复或重新验证接入；不能跳过签名校验'}


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
