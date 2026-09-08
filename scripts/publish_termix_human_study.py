"""Publish identity-redacted study copies; retain original downloads privately."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TASKS = ('live-20260908-grid', 'live-20260908-yield', 'live-20260908-health-followup')


def encoded(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main() -> None:
    private = ROOT / '.data/termix-study-2026-09-08'
    inventory = json.loads((private / '记录清单.json').read_text())
    source = private / '原始记录-请勿公开'
    dest = ROOT / 'evidence/termix/human-study'
    publications = []
    for task_id in TASKS:
        row = next(item for item in inventory['pairs'] if item['task_id'] == task_id)
        original = (source / task_id / 'manual-output.json').read_bytes()
        manual = json.loads(original)
        agent_bytes = (ROOT / f'evidence/termix/raw/{task_id}/agent-output.json').read_bytes()
        agent = json.loads(agent_bytes)
        task = json.loads((ROOT / f'evidence/termix/tasks/{task_id}.json').read_text())
        if (hashlib.sha256(original).hexdigest() != row['manual_raw_sha256']
                or hashlib.sha256(agent_bytes).hexdigest() != row['agent_raw_sha256']
                or manual['task_snapshot'] != task or agent['task_snapshot'] != task
                or manual['evidence_mode'] != 'human_timed_manual_run'
                or manual['duration_seconds'] <= 0 or not manual['output'].strip()):
            raise ValueError('Raw evidence or task binding mismatch')
        # Do not publish names/handles; answer text and original times are unchanged.
        public_manual = {key: value for key, value in manual.items() if key != 'operator'}
        public_manual['redactions'] = ['operator']
        public_manual['original_private_file_sha256'] = row['manual_raw_sha256']
        public_manual['authenticity_boundary'] = 'Participant self-attestation, not independently observed or authenticated.'
        pair = {'schema_version': 'safehire-termix-public-pair/1', 'task_id': task_id,
                'task_snapshot': task, 'manual': public_manual, 'agent': agent,
                'boundary': 'Operator field removed; human answer text unchanged. Original private file hash identifies the unredacted export. Sponsored deterministic Agent analysis, not paid external delivery.'}
        body = encoded(pair)
        report_row = {**row, 'pair_sha256': hashlib.sha256(body).hexdigest(),
                      'pair_url': f'/api/evidence/termix/human-study/{task_id}'}
        publications.append((task_id, body, report_row))
    dest.mkdir(parents=True, exist_ok=True)
    for task_id, body, _ in publications:
        (dest / f'{task_id}.json').write_bytes(body)
    report = {**inventory, 'schema_version': 'safehire-termix-public-study/1',
              'pairs': [row for _, _, row in publications],
              'report_url': '/api/evidence/termix/human-study',
              'independent_review': 'not_available', 'quality_score': None,
              'quality_assessment': {
                  'method': 'Entrant AI-assisted formula and completeness check; not independent human scoring.',
                  'numeric_findings': 'Reported grid levels, yield calculations and health-factor/repayment figures agree with the supplied formulas at displayed precision.',
                  'manual_omissions': {'grid': 'Execution prerequisites and whether drawdown is enforced are missing.',
                                       'yield': 'Explicit ranking conclusion and changing-rate/cost/return limitations are missing.',
                                       'health-followup': 'Future liquidation-risk explanation is missing.'},
                  'agent_limitations': 'Risk labels are not full explanations. TVL zero is an unknown-input placeholder. All outputs are deterministic previews without execution authority.'},
              'comparison_claim': 'Descriptive records only. No end-to-end speedup, superiority, profit or eligibility claim.',
              'privacy': 'Operator names removed from public copies; exact original exports retained privately.'}
    (dest / 'report.json').write_bytes(encoded(report))
    print('Published three identity-redacted pairs; no scores invented.')


if __name__ == '__main__':
    main()
