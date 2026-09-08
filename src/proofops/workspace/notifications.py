"""Opt-in Bark delivery. Keys stay encrypted; acceptance is not human receipt."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import secrets
import sqlite3
import time
from typing import Any

import httpx
from Crypto.Cipher import AES

from proofops.workspace.store import Journal


class Notifications:
    def __init__(self, journal: Journal):
        self.journal = journal
        self.key_path = journal.path.parent / 'notification.key'
        with journal.db() as db:
            db.executescript('''
              CREATE TABLE IF NOT EXISTS push_channels(space TEXT PRIMARY KEY,secret TEXT,enabled INTEGER,
                verified INTEGER,code_hash TEXT,deadline REAL,attempts INTEGER,updated REAL,generation TEXT);
              CREATE TABLE IF NOT EXISTS push_outbox(id INTEGER PRIMARY KEY AUTOINCREMENT,space TEXT,
                event INTEGER UNIQUE,watch TEXT,state TEXT,attempts INTEGER DEFAULT 0,due REAL,lease REAL DEFAULT 0,
                created REAL,finished REAL,error TEXT,generation TEXT);
            ''')

    def _key(self) -> bytes:
        if self.key_path.is_symlink():
            raise ValueError('Invalid notification key file')
        if not self.key_path.exists():
            try:
                fd=os.open(self.key_path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
                with os.fdopen(fd,'wb') as f:f.write(secrets.token_bytes(32))
            except FileExistsError:pass
        key=self.key_path.read_bytes()
        if len(key)!=32 or self.key_path.stat().st_mode & 0o077:
            raise ValueError('Notification key unavailable or permissions unsafe')
        return key

    def seal(self, space: str, key: str) -> str:
        cipher=AES.new(self._key(),AES.MODE_GCM,nonce=secrets.token_bytes(12))
        cipher.update(space.encode())
        ciphertext,tag=cipher.encrypt_and_digest(key.encode())
        return base64.b64encode(bytes(cipher.nonce)+tag+ciphertext).decode()

    def unseal(self, space: str, value: str) -> str:
        blob=base64.b64decode(value,validate=True)
        cipher=AES.new(self._key(),AES.MODE_GCM,nonce=blob[:12]);cipher.update(space.encode())
        return str(cipher.decrypt_and_verify(blob[28:],blob[12:28]).decode())

    def status(self, space: str) -> dict[str, Any]:
        with self.journal.db() as db:
            c=db.execute('SELECT enabled,verified,deadline,updated,LENGTH(secret)>0 AS has_secret FROM push_channels WHERE space=?',(space,)).fetchone()
            rows=[dict(r) for r in db.execute('SELECT id,event,watch,state,attempts,created,finished,error FROM push_outbox WHERE space=? ORDER BY id DESC LIMIT 30',(space,))]
        return {'channel':'bark','bound':bool(c and c['has_secret']),'enabled':bool(c and c['enabled']),
                'verified':bool(c and c['verified']),'verification_deadline':c['deadline'] if c else None,
                'deliveries':rows,'boundary':'Provider acceptance is not proof a person read the alert. After unsubscribe an already in-flight request may still arrive.'}

    async def bind(self, space: str, key: str) -> dict[str, Any]:
        now=time.time();code=f'{secrets.randbelow(1000000):06d}';generation=secrets.token_hex(16)
        sealed=self.seal(space,key)
        with self.journal.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT updated FROM push_channels WHERE space=?',(space,)).fetchone()
            if old and now-old['updated']<60:raise ValueError('Wait one minute before sending another verification notification.')
            db.execute('INSERT OR REPLACE INTO push_channels VALUES(?,?,0,0,?,?,0,?,?)',
                       (space,sealed,hashlib.sha256(code.encode()).hexdigest(),now+900,now,generation))
            db.execute("UPDATE push_outbox SET state='cancelled' WHERE space=? AND state IN ('pending','sending')",(space,))
            db.execute('COMMIT')
        accepted=await send_bark(key,'SafeHire: verify your device',f'Verification code: {code}. Enter it only in the SafeHire workspace you just opened. Valid for 15 minutes. This is a test, not a risk alert.')
        return {'provider_accepted':accepted,'phone_receipt_verified':False,'expires_in_seconds':900}

    def verify(self, space: str, code: str) -> None:
        with self.journal.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row=db.execute('SELECT * FROM push_channels WHERE space=?',(space,)).fetchone()
            if not row or row['deadline']<time.time() or row['attempts']>=5 or row['verified']:
                raise ValueError('The verification code expired. Bind the device again.')
            db.execute('UPDATE push_channels SET attempts=attempts+1 WHERE space=?',(space,))
            valid=secrets.compare_digest(row['code_hash'],hashlib.sha256(code.encode()).hexdigest())
            if valid:db.execute("UPDATE push_channels SET enabled=1,verified=1,code_hash='',updated=? WHERE space=?",(time.time(),space))
            db.execute('COMMIT')
        if not valid:raise ValueError('Incorrect verification code.')

    def unsubscribe(self, space: str) -> None:
        with self.journal.db() as db:
            db.execute('BEGIN IMMEDIATE')
            # Keep rate-limit metadata, erase encrypted destination and invalidate pending OTP.
            db.execute("UPDATE push_channels SET secret='',enabled=0,verified=0,code_hash='',deadline=0 WHERE space=?",(space,))
            db.execute("UPDATE push_outbox SET state='cancelled' WHERE space=? AND state IN ('pending','sending')",(space,))
            db.execute('COMMIT')

    def enqueue(self) -> None:
        now=time.time()
        with self.journal.db() as db:
            db.execute('''INSERT OR IGNORE INTO push_outbox(space,event,watch,state,due,created,generation)
              SELECT w.space,e.seq,w.id,'pending',?, ?,c.generation FROM events e
              JOIN watches w ON w.id=e.watch JOIN push_channels c ON c.space=w.space
              WHERE c.enabled=1 AND c.verified=1 AND w.active=1 AND e.kind IN ('alert','delivery_ready')
              AND e.at>=c.updated AND e.at>=?''',(now,now,now-1800))
            db.execute("UPDATE push_outbox SET state='expired' WHERE state IN ('pending','sending') AND created<?",(now-1800,))
            db.execute("DELETE FROM push_outbox WHERE created<? AND state NOT IN ('pending','sending')",(now-7*86400,))

    async def deliver_one(self) -> bool:
        now=time.time()
        with self.journal.db() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("UPDATE push_outbox SET state='failed',error='attempt_limit_after_restart' WHERE state='sending' AND lease<=? AND attempts>=3", (now,))
            row=db.execute('''SELECT o.*,c.secret,w.kind AS category FROM push_outbox o
              JOIN push_channels c ON c.space=o.space JOIN watches w ON w.id=o.watch
              WHERE o.state IN ('pending','sending') AND o.attempts<3 AND o.due<=? AND o.lease<=?
              AND c.enabled=1 AND c.verified=1 AND c.generation=o.generation AND w.active=1
              AND NOT EXISTS (SELECT 1 FROM push_outbox p WHERE p.space=o.space AND p.id!=o.id
                AND p.state='accepted_by_provider' AND p.finished>?)
              ORDER BY o.id LIMIT 1''',(now,now,now-60)).fetchone()
            if not row:
                db.execute('COMMIT');return False
            db.execute("UPDATE push_outbox SET state='sending',lease=?,attempts=attempts+1 WHERE id=?",(now+45,row['id']))
            db.execute('COMMIT')
        error=None
        try:
            key=self.unseal(row['space'],row['secret'])
            labels={'health':'Lending risk','lp':'LP positions','yield':'Yield comparison','grid':'Grid range','order':'Service order'}
            accepted=await send_bark(key,'SafeHire: review a new alert',f"{labels.get(row['category'],'Task')} has a new update or alert. Open your workspace for the latest status. This notification does not mean any action was executed. Alert ID {row['id']}。")
            if not accepted:error='push_provider_rejected'
        except (ValueError,OSError):error='notification_key_unavailable'
        with self.journal.db() as db:
            state='accepted_by_provider' if error is None else 'failed' if row['attempts']+1>=3 else 'pending'
            db.execute('''UPDATE push_outbox SET state=?,lease=0,due=?,finished=?,error=?
              WHERE id=? AND state='sending' AND generation=?''',
                       (state,time.time()+60*(2**row['attempts']),time.time() if state!='pending' else None,error,row['id'],row['generation']))
        return True


async def send_bark(key: str, title: str, body: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=15,follow_redirects=False) as client:
            r=await client.post('https://api.day.app/push',json={'device_key':key,'title':title,'body':body,
                 'group':'SafeHire alerts','url':'https://safehire.eyesonchain.xyz/workspace','isArchive':'0'})
            payload=r.json()
            return bool(r.status_code==200 and isinstance(payload,dict) and payload.get('code')==200)
    except (httpx.HTTPError,ValueError):return False


async def run(journal: Journal) -> None:
    n=Notifications(journal)
    while True:
        try:
            n.enqueue()
            if not await n.deliver_one():await asyncio.sleep(5)
        except (sqlite3.Error,OSError,ValueError) as exc:
            logging.getLogger(__name__).warning('Notification worker unavailable: %s',type(exc).__name__)
            await asyncio.sleep(15)
