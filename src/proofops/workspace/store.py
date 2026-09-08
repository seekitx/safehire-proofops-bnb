from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any


class Journal:
    def __init__(self, path: Path) -> None:
        if path.is_symlink():
            raise ValueError('Journal must not be a symlink')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path = path
        with self.db() as db:
            db.executescript('''
              PRAGMA journal_mode=WAL;
              CREATE TABLE IF NOT EXISTS spaces(id TEXT PRIMARY KEY, secret TEXT, created REAL);
              CREATE TABLE IF NOT EXISTS watches(
                id TEXT PRIMARY KEY, space TEXT, kind TEXT, spec TEXT, active INTEGER,
                created REAL, expires REAL, due REAL, lease REAL DEFAULT 0,
                attempts INTEGER DEFAULT 0, latest TEXT DEFAULT '{}', state TEXT DEFAULT 'pending',
                UNIQUE(space,kind,spec));
              CREATE TABLE IF NOT EXISTS notify_attempts(job INTEGER PRIMARY KEY, attempts INTEGER, next_at REAL);
              CREATE TABLE IF NOT EXISTS events(
                seq INTEGER PRIMARY KEY AUTOINCREMENT, watch TEXT, at REAL, kind TEXT, data TEXT,
                read_at REAL);
              CREATE INDEX IF NOT EXISTS watch_due ON watches(active,due,lease);
              CREATE INDEX IF NOT EXISTS event_watch ON events(watch,seq);
            ''')
        path.chmod(0o600)

    @contextmanager
    def db(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            yield db
        finally:
            db.close()

    def create_space(self) -> dict[str, str]:
        identifier, token = uuid.uuid4().hex, secrets.token_urlsafe(32)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT count(*) FROM spaces').fetchone()[0] >= 500:
                raise ValueError('Workspace quota reached')
            db.execute('INSERT INTO spaces VALUES(?,?,?)', (identifier, hashlib.sha256(token.encode()).hexdigest(), time.time()))
            db.execute('COMMIT')
        return {'space_id': identifier, 'token': token, 'scope': 'private journal only, not wallet authority'}

    def authorize(self, space: str, token: str) -> None:
        with self.db() as db:
            row = db.execute('SELECT secret FROM spaces WHERE id=?', (space,)).fetchone()
        if not row or not secrets.compare_digest(row['secret'], hashlib.sha256(token.encode()).hexdigest()):
            raise LookupError('Workspace not found')

    def add(self, space: str, kind: str, spec: dict[str, Any], *, now: float | None = None) -> str:
        now = time.time() if now is None else now
        raw = json.dumps(spec, sort_keys=True, separators=(',', ':'), allow_nan=False)
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT id FROM watches WHERE space=? AND kind=? AND spec=?', (space, kind, raw)).fetchone()
            if old:
                return str(old['id'])
            if db.execute('SELECT count(*) FROM watches').fetchone()[0] >= 200 or db.execute('SELECT count(*) FROM watches WHERE space=?', (space,)).fetchone()[0] >= 10:
                raise ValueError('Watch quota reached')
            identifier = uuid.uuid4().hex
            # Public order recovery remains available after the private follow-up expires.
            ttl = 10 * 86400 if kind == 'order' else 86400
            db.execute('INSERT INTO watches(id,space,kind,spec,active,created,expires,due) VALUES(?,?,?,?,1,?,?,?)', (identifier, space, kind, raw, now, now+ttl, now))
            db.execute('INSERT INTO events(watch,at,kind,data) VALUES(?,?,?,?)', (identifier, now, 'created', json.dumps({'spec': spec, 'expires': now+ttl})))
            db.execute('COMMIT')
        return identifier

    def list(self, space: str) -> list[dict[str, Any]]:
        with self.db() as db:
            rows = db.execute('SELECT * FROM watches WHERE space=? ORDER BY created DESC', (space,)).fetchall()
            result = []
            for r in rows:
                row = dict(r)
                row['spec'], row['latest'] = json.loads(row['spec']), json.loads(row['latest'])
                row['events'] = [dict(e) | {'data': json.loads(e['data'])} for e in db.execute('SELECT * FROM events WHERE watch=? ORDER BY seq DESC LIMIT 300', (row['id'],))]
                row['history_limit'] = 300
                result.append(row)
            return result

    def pause(self, space: str, watch: str) -> None:
        with self.db() as db:
            if not db.execute('UPDATE watches SET active=0 WHERE id=? AND space=?', (watch, space)).rowcount:
                raise LookupError('Watch not found')

    def acknowledge(self, space: str, watch: str) -> None:
        with self.db() as db:
            db.execute('UPDATE events SET read_at=? WHERE watch=? AND read_at IS NULL AND EXISTS(SELECT 1 FROM watches WHERE id=? AND space=?)', (time.time(), watch, watch, space))

    def claim(self, *, now: float | None = None) -> dict[str, Any] | None:
        now = time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE watches SET active=0,state='expired' WHERE active=1 AND expires<=?", (now,))
            row = db.execute('SELECT * FROM watches WHERE active=1 AND due<=? AND lease<=? ORDER BY due LIMIT 1', (now, now)).fetchone()
            if not row:
                db.execute('COMMIT')
                return None
            db.execute('UPDATE watches SET lease=? WHERE id=?', (now+180, row['id']))
            db.execute('COMMIT')
        return dict(row) | {'spec': json.loads(row['spec']), 'latest': json.loads(row['latest'])}

    def reserve_notification(self, job_id: int, *, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM notify_attempts WHERE job=?', (job_id,)).fetchone()
            if row and (row['attempts'] >= 3 or row['next_at'] > now):
                return False
            attempts = row['attempts']+1 if row else 1
            db.execute('INSERT INTO notify_attempts VALUES(?,?,?) ON CONFLICT(job) DO UPDATE SET attempts=excluded.attempts,next_at=excluded.next_at', (job_id, attempts, now+300))
            db.execute('COMMIT')
        return True

    def finish(self, watch: str, state: str, data: dict[str, Any], *, interval: int = 300,
               attempted: bool = False, terminal: bool = False, now: float | None = None) -> None:
        now = time.time() if now is None else now
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT state FROM watches WHERE id=?', (watch,)).fetchone()
            if not row:
                raise LookupError('Watch not found')
            raw = json.dumps(data, ensure_ascii=False, allow_nan=False)
            db.execute('UPDATE watches SET latest=?,state=?,due=?,lease=0,attempts=attempts+?,active=CASE WHEN ? THEN 0 ELSE active END WHERE id=?', (raw, state, now+interval, int(attempted), terminal, watch))
            kind = 'alert' if state in {'alert', 'error', 'acceptance_failed', 'overdue'} and row['state'] != state else 'observation'
            db.execute('INSERT INTO events(watch,at,kind,data) VALUES(?,?,?,?)', (watch, now, kind, raw))
            # Explicit retention bound; downloadable evidence states the limit.
            db.execute('DELETE FROM events WHERE watch=? AND seq NOT IN (SELECT seq FROM events WHERE watch=? ORDER BY seq DESC LIMIT 300)', (watch, watch))
            db.execute('COMMIT')

    def watch(self, space: str, watch: str) -> dict[str, Any]:
        rows = self.list(space)
        row = next((r for r in rows if r['id'] == watch), None)
        if row is None:
            raise LookupError('Watch not found')
        return row

    def resume(self, space: str, watch: str) -> None:
        now = time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT kind,state FROM watches WHERE id=? AND space=?', (watch, space)).fetchone()
            if not row:
                raise LookupError('Watch not found')
            if row['kind'] == 'order' and row['state'] in {'completed', 'rejected'}:
                raise ValueError('Terminal order cannot be resumed')
            ttl = 864000 if row['kind'] == 'order' else 86400
            db.execute('UPDATE watches SET active=1,expires=?,due=? WHERE id=?', (now+ttl, now, watch))
            db.execute("INSERT INTO events(watch,at,kind,data) VALUES(?,?,'resumed',?)", (watch, now, json.dumps({'expires':now+ttl,'chain_deadline_changed':False})))
            db.execute('COMMIT')

    def save_action(self, space: str, watch: str, value: dict[str, Any]) -> None:
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM watches WHERE id=? AND space=?', (watch, space)).fetchone():
                raise LookupError('Watch not found')
            if db.execute("SELECT count(*) FROM events WHERE watch=? AND kind='action_plan'", (watch,)).fetchone()[0] >= 20:
                raise ValueError('Action preparation limit reached for this watch')
            db.execute("INSERT INTO events(watch,at,kind,data) VALUES(?,?,'action_plan',?)", (watch,time.time(),json.dumps(value,allow_nan=False)))
            db.execute('COMMIT')

    def save_provider_probe(self, token: int, value: dict[str, Any]) -> None:
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS provider_probes(token INTEGER PRIMARY KEY,data TEXT)')
            db.execute('INSERT INTO provider_probes VALUES(?,?) ON CONFLICT(token) DO UPDATE SET data=excluded.data', (token,json.dumps(value,allow_nan=False)))

    def provider_probes(self) -> dict[int, dict[str, Any]]:
        with self.db() as db:
            db.execute('CREATE TABLE IF NOT EXISTS provider_probes(token INTEGER PRIMARY KEY,data TEXT)')
            return {r['token']:json.loads(r['data']) for r in db.execute('SELECT token,data FROM provider_probes')}
