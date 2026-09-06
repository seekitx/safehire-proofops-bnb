"""Private, bounded SQLite task journal with optimistic concurrency.

A task token is a capability to THIS local analysis record, not a wallet signature.
Hash chains detect edits relative to an exported head; they are not immutable and
cannot detect a privileged operator restoring an older complete database alone.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from proofops.arena.models import Proposal, TaskSpec, canonical, digest, utcnow
from proofops.arena.planners import evaluate


class Conflict(ValueError):
    pass


class MissingTask(LookupError):
    pass


class CapacityError(ValueError):
    pass


def parse_proposal(text: str) -> Proposal:
    if not 1 <= len(text.encode('utf-8')) <= 24000:
        raise ValueError('proposal must be 1..24,000 UTF-8 bytes')

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            if key in result:
                raise ValueError('duplicate JSON keys are forbidden')
            result[key] = value
        return result

    try:
        decoded = json.loads(text, object_pairs_hook=pairs)
    except RecursionError as exc:
        raise ValueError('proposal JSON nesting exceeds supported depth') from exc
    return Proposal.model_validate(decoded)


class TaskStore:
    def __init__(self, path: Path, *, max_tasks: int = 2000, max_proposals: int = 10) -> None:
        self.path, self.max_tasks, self.max_proposals = path, max_tasks, max_proposals
        if path.is_symlink():
            raise ValueError('database must not be a symlink')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
              CREATE TABLE IF NOT EXISTS arena_tasks (
                task_id TEXT PRIMARY KEY, token_hash TEXT NOT NULL, task_json TEXT NOT NULL,
                task_hash TEXT NOT NULL, version INTEGER NOT NULL, created_at TEXT NOT NULL);
              CREATE TABLE IF NOT EXISTS arena_proposals (
                task_id TEXT NOT NULL, proposal_id TEXT NOT NULL, request_key TEXT NOT NULL,
                raw_text TEXT NOT NULL, raw_sha256 TEXT NOT NULL, proposal_hash TEXT NOT NULL,
                report_json TEXT NOT NULL, source_mode TEXT NOT NULL, version INTEGER NOT NULL,
                PRIMARY KEY(task_id, proposal_id), UNIQUE(task_id, request_key),
                FOREIGN KEY(task_id) REFERENCES arena_tasks(task_id));
              CREATE TABLE IF NOT EXISTS arena_events (
                task_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_json TEXT NOT NULL,
                previous_hash TEXT NOT NULL, event_hash TEXT NOT NULL,
                PRIMARY KEY(task_id,sequence), FOREIGN KEY(task_id) REFERENCES arena_tasks(task_id));
            ''')
        path.chmod(0o600)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('PRAGMA busy_timeout=5000')
        try:
            yield db
        finally:
            db.close()

    def _event(self, db: sqlite3.Connection, task_id: str, kind: str, data: dict[str, Any], now: datetime) -> None:
        previous = db.execute('SELECT sequence,event_hash FROM arena_events WHERE task_id=? ORDER BY sequence DESC LIMIT 1', (task_id,)).fetchone()
        sequence, head = (previous['sequence'] + 1, previous['event_hash']) if previous else (1, '0' * 64)
        value = {'schema': 'safehire-local-event/2', 'task_id': task_id, 'sequence': sequence,
                 'kind': kind, 'observed_at': now.isoformat(), 'data': data, 'previous_hash': head}
        db.execute('INSERT INTO arena_events VALUES(?,?,?,?,?)', (task_id, sequence, canonical(value), head, digest(value)))

    def create(self, task: TaskSpec, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or utcnow()
        if not task.fresh(now):
            raise ValueError('cannot open task against stale/future snapshot')
        task_id, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                if db.execute('SELECT count(*) FROM arena_tasks').fetchone()[0] >= self.max_tasks:
                    raise CapacityError('task capacity reached; archive locally or increase configured quota')
                db.execute('INSERT INTO arena_tasks VALUES(?,?,?,?,?,?)',
                           (task_id, hashlib.sha256(token.encode()).hexdigest(), canonical(task.to_dict()), task.task_hash, 1, now.isoformat()))
                self._event(db, task_id, 'task_opened', {'task_hash': task.task_hash}, now)
                db.execute('COMMIT')
            except Exception:
                db.execute('ROLLBACK')
                raise
        return {'task_id': task_id, 'task_token': token, 'version': 1, 'task_hash': task.task_hash,
                'token_scope': 'private_local_analysis_record_only_not_wallet_authority'}

    def _get(self, db: sqlite3.Connection, task_id: str, token: str) -> sqlite3.Row:
        row = db.execute('SELECT * FROM arena_tasks WHERE task_id=?', (task_id,)).fetchone()
        actual = hashlib.sha256(token.encode()).hexdigest()
        if row is None or not secrets.compare_digest(row['token_hash'], actual):
            raise MissingTask('task not found or capability token invalid')
        return cast(sqlite3.Row, row)

    def submit(self, task_id: str, token: str, proposal_text: str, *, request_key: str,
               expected_version: int, now: datetime | None = None) -> dict[str, Any]:
        if not 8 <= len(request_key) <= 128 or not request_key.isascii():
            raise ValueError('idempotency key must be 8..128 ASCII characters')
        proposal = parse_proposal(proposal_text)
        raw_hash = hashlib.sha256(proposal_text.encode()).hexdigest()
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            try:
                row = self._get(db, task_id, token)
                old = db.execute('SELECT * FROM arena_proposals WHERE task_id=? AND request_key=?', (task_id, request_key)).fetchone()
                if old:
                    if old['raw_sha256'] != raw_hash:
                        raise Conflict('idempotency key reused with different exact output bytes')
                    db.execute('COMMIT')
                    return {'proposal_id': old['proposal_id'], 'version': old['version'],
                            'report': json.loads(old['report_json']), 'replayed': True}
                if type(expected_version) is not int or row['version'] != expected_version:
                    raise Conflict('task version changed; reload task before retrying')
                if db.execute('SELECT count(*) FROM arena_proposals WHERE task_id=?', (task_id,)).fetchone()[0] >= self.max_proposals:
                    raise CapacityError('proposal capacity reached for task')
                task = TaskSpec.model_validate_json(row['task_json'])
                report = evaluate(task, proposal, now=now)
                proposal_id, version = uuid.uuid4().hex, row['version'] + 1
                # Input does NOT select provenance: all public imports stay caller supplied.
                db.execute('INSERT INTO arena_proposals VALUES(?,?,?,?,?,?,?,?,?)',
                           (task_id, proposal_id, request_key, proposal_text, raw_hash,
                            proposal.proposal_hash, canonical(report), 'caller_import', version))
                db.execute('UPDATE arena_tasks SET version=? WHERE task_id=?', (version, task_id))
                self._event(db, task_id, 'proposal_checked', {'proposal_id': proposal_id, 'raw_sha256': raw_hash,
                            'proposal_hash': proposal.proposal_hash, 'report_hash': digest(report),
                            'source_mode': 'caller_import'}, now or utcnow())
                db.execute('COMMIT')
            except Exception:
                if db.in_transaction:
                    db.execute('ROLLBACK')
                raise
        return {'proposal_id': proposal_id, 'version': version, 'report': report, 'replayed': False}

    def bundle(self, task_id: str, token: str) -> dict[str, Any]:
        with self.connect() as db:
            db.execute('BEGIN')
            row = self._get(db, task_id, token)
            proposals = [dict(v) for v in db.execute('SELECT proposal_id,raw_text,raw_sha256,proposal_hash,report_json,source_mode,version FROM arena_proposals WHERE task_id=? ORDER BY version', (task_id,))]
            events = [dict(v) for v in db.execute('SELECT sequence,event_json,event_hash,previous_hash FROM arena_events WHERE task_id=? ORDER BY sequence', (task_id,))]
            db.execute('COMMIT')
        bundle = {'schema_version': 'safehire-private-bundle/2', 'task_id': task_id,
                  'version': row['version'], 'task': json.loads(row['task_json']), 'task_hash': row['task_hash'],
                  'proposals': proposals, 'events': events,
                  'evidence_mode': 'private_caller_supplied_analysis',
                  'paid_delivery_verified': False, 'agent_authorship_verified': False,
                  'trust_boundary': 'Local journal. Preserve exported head outside the database; not an onchain attestation.'}
        bundle['integrity'] = verify_bundle(bundle)
        bundle['bundle_sha256'] = digest(bundle)
        return bundle


def verify_bundle(bundle: dict[str, Any], *, trusted_head: str | None = None) -> dict[str, Any]:
    """Offline verification, including exact output bytes and their event bindings."""
    failures: list[str] = []
    try:
        if bundle.get('schema_version') != 'safehire-private-bundle/2':
            failures.append('schema_version')
        task = TaskSpec.model_validate(bundle['task'])
        if task.task_hash != bundle['task_hash']:
            failures.append('task_hash')
        head, referenced = '0' * 64, {}
        events = bundle['events']
        if not events:
            failures.append('missing_events')
        for expected_sequence, row in enumerate(events, 1):
            event = json.loads(row['event_json'])
            if row['sequence'] != expected_sequence or event['sequence'] != expected_sequence:
                failures.append('sequence')
            if event['task_id'] != bundle['task_id'] or row['previous_hash'] != head or event['previous_hash'] != head:
                failures.append('chain_link')
            if digest(event) != row['event_hash']:
                failures.append('event_hash')
            if expected_sequence == 1 and (event['kind'] != 'task_opened' or event['data'].get('task_hash') != task.task_hash):
                failures.append('task_binding')
            if event['kind'] == 'proposal_checked':
                if expected_sequence == 1 or event['data']['proposal_id'] in referenced:
                    failures.append('duplicate_or_misordered_proposal')
                referenced[event['data']['proposal_id']] = {**event['data'], 'version': expected_sequence}
            elif event['kind'] != 'task_opened' or expected_sequence != 1:
                failures.append('unknown_event')
            head = row['event_hash']
        if len(events) != bundle['version']:
            failures.append('head_version')
        if len(referenced) != len(bundle['proposals']):
            failures.append('missing_proposal')
        if len({p['proposal_id'] for p in bundle['proposals']}) != len(bundle['proposals']):
            failures.append('duplicate_proposal')
        for proposal in bundle['proposals']:
            ref = referenced.get(proposal['proposal_id'], {})
            if proposal['version'] != ref.get('version'):
                failures.append('proposal_version')
            raw = hashlib.sha256(proposal['raw_text'].encode()).hexdigest()
            normalized = parse_proposal(proposal['raw_text']).proposal_hash
            report_hash = digest(json.loads(proposal['report_json']))
            if raw != proposal['raw_sha256'] or raw != ref.get('raw_sha256'):
                failures.append('output_bytes')
            if normalized != proposal['proposal_hash'] or normalized != ref.get('proposal_hash'):
                failures.append('proposal_hash')
            if report_hash != ref.get('report_hash') or proposal['source_mode'] != ref.get('source_mode'):
                failures.append('report_binding')
        if trusted_head is not None and head != trusted_head:
            failures.append('external_head_mismatch')
        if 'bundle_sha256' in bundle:
            exported = {k: v for k, v in bundle.items() if k != 'bundle_sha256'}
            if digest(exported) != bundle['bundle_sha256']:
                failures.append('bundle_sha256')
        return {'valid': not failures, 'failures': sorted(set(failures)), 'head': head,
                'external_anchor_checked': trusted_head is not None,
                'authorship_or_chain_truth_verified': False}
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError, AttributeError) as exc:
        return {'valid': False, 'failures': ['malformed_bundle'], 'error_type': type(exc).__name__,
                'external_anchor_checked': trusted_head is not None,
                'authorship_or_chain_truth_verified': False}
