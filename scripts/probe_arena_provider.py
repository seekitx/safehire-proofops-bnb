"""Read-only signed-quote compatibility probe. Never fund or notify a paid job.

Uses a public synthetic task: no wallet address, no user portfolio is transmitted.
A successful quote is NOT evidence that a supplier produced the requested delivery.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec
from proofops.services.live_agent_market import request_live_agent_quote


async def main() -> None:
    task = TaskSpec.model_validate(examples()['tasks']['yield_optimisation'])
    try:
        result = await request_live_agent_quote(
            Path(__file__).resolve().parents[1], skill_id='yield_plan',
            agent_token_id=304493,
            task_input={'amountUsd': 1000, 'currentApyPct': 5},
            arena_task=task.to_dict(),
        )
    except (ValueError, TypeError, KeyError, OSError, httpx.HTTPError) as exc:
        print(json.dumps({'signed_quote_compatible': False, 'error_type': type(exc).__name__,
                          'reason': str(exc), 'synthetic_task': True,
                          'delivery_format_verified': False, 'transaction_sent': False}))
        raise SystemExit(1) from None
    print(json.dumps({
        'observed_at': result['observed_at'], 'signed_quote_compatible': True,
        'synthetic_task': True, 'task_hash': task.task_hash, 'quote': result['quote'],
        'verification': result['quote_verification'],
        'delivery_format_verified': False, 'transaction_sent': False,
        'boundary': 'Quote terms and signature only. Actual structured delivery still requires a funded job or supplier-provided integration sample.',
    }, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
