"""Capture sponsored public Agent responses, without inventing manual runs or scores."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


async def main(task_ids: list[str]) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        for task_id in task_ids:
            if not re.fullmatch(r'live-[0-9]{8}-[a-z0-9-]+', task_id):
                raise ValueError('Invalid task identifier')
            task = json.loads((ROOT / f'evidence/termix/tasks/{task_id}.json').read_text())
            target = ROOT / f'evidence/termix/raw/{task_id}/agent-output.json'
            if target.exists():
                raise ValueError('Existing raw output is immutable; do not overwrite it')
            request = {'jsonrpc': '2.0', 'id': task_id, 'method': 'message/send', 'params': {
                'message': {'role': 'user', 'messageId': task_id,
                            'parts': [{'kind': 'data', 'data': task['agent_request']}]}}}
            start = datetime.now(UTC).isoformat()
            clock = time.perf_counter()
            response = await client.post('https://safehire.eyesonchain.xyz/a2a', json=request)
            elapsed = time.perf_counter() - clock
            response.raise_for_status()
            result = response.json()
            if result.get('result', {}).get('status') != 'completed' or not result['result'].get('hire_receipt', {}).get('record_hash'):
                raise ValueError('Sponsored Agent did not produce a completed receipt')
            record = {'schema_version': 'safehire-termix-agent/2', 'evidence_mode': 'sponsored',
                      'task_id': task_id, 'task_snapshot': task, 'request': request,
                      'response': result, 'raw_response_text': response.text,
                      'raw_response_sha256': hashlib.sha256(response.content).hexdigest(),
                      'started_at': start, 'finished_at': datetime.now(UTC).isoformat(),
                      'duration_seconds': elapsed, 'cost': {'amount': 0, 'currency': 'U', 'mode': 'sponsored'},
                      'boundary': 'Actual public first-party sponsored analysis. No paid job, no independent supplier, no executed strategy. Timing excludes shared source collection and participant setup; no human score generated.'}
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x') as stream:
                stream.write(json.dumps(record, ensure_ascii=False, indent=2) + '\n')
            print(task_id, 'completed', round(elapsed, 3), 'seconds; 0 U sponsored')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--task', action='append', dest='tasks')
    args = parser.parse_args()
    asyncio.run(main(args.tasks or ['live-20260908-health', 'live-20260908-grid', 'live-20260908-yield']))
