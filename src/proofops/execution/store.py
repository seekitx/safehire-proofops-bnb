from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proofops.domain.errors import DuplicateRequestError
from proofops.domain.models import PermissionPolicy, TaskState


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    agent_id: str
    policy_id: str
    state: TaskState
    request: Mapping[str, Any]
    simulation: Mapping[str, Any] | None
    receipt: Mapping[str, Any] | None
    created_at: str
    updated_at: str
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "policy_id": self.policy_id,
            "state": self.state.value,
            "request": dict(self.request),
            "simulation": dict(self.simulation) if self.simulation else None,
            "receipt": dict(self.receipt) if self.receipt else None,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }


class SQLiteStore:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    policy_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    simulation_json TEXT,
                    receipt_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS policies (
                    policy_id TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    chain_id INTEGER NOT NULL,
                    allowed_targets_json TEXT NOT NULL,
                    allowed_methods_json TEXT NOT NULL,
                    max_value_usd REAL NOT NULL,
                    daily_value_usd REAL NOT NULL,
                    max_slippage_bps INTEGER NOT NULL,
                    expires_at TEXT NOT NULL,
                    require_human_approval INTEGER NOT NULL,
                    revoked INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS idempotency (
                    idempotency_key TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS policy_spend (
                    policy_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    spent_usd REAL NOT NULL DEFAULT 0,
                    PRIMARY KEY(policy_id, day)
                );
                CREATE TABLE IF NOT EXISTS flags (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS wallet_challenges (
                    owner TEXT PRIMARY KEY,
                    message TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS wallet_sessions (
                    token_hash TEXT PRIMARY KEY,
                    owner TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _policy_from_row(row: sqlite3.Row) -> PermissionPolicy:
        return PermissionPolicy(
            policy_id=str(row["policy_id"]),
            owner=str(row["owner"]),
            agent_id=str(row["agent_id"]),
            chain_id=int(row["chain_id"]),
            allowed_targets=tuple(json.loads(row["allowed_targets_json"])),
            allowed_methods=tuple(json.loads(row["allowed_methods_json"])),
            max_value_usd=float(row["max_value_usd"]),
            daily_value_usd=float(row["daily_value_usd"]),
            max_slippage_bps=int(row["max_slippage_bps"]),
            expires_at=datetime.fromisoformat(str(row["expires_at"])),
            require_human_approval=bool(row["require_human_approval"]),
            revoked=bool(row["revoked"]),
        )

    def save_policy(self, policy: PermissionPolicy) -> PermissionPolicy:
        now = self._now()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO policies(
                    policy_id, owner, agent_id, chain_id, allowed_targets_json,
                    allowed_methods_json, max_value_usd, daily_value_usd,
                    max_slippage_bps, expires_at, require_human_approval,
                    revoked, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(policy_id) DO UPDATE SET
                    owner=excluded.owner,
                    agent_id=excluded.agent_id,
                    chain_id=excluded.chain_id,
                    allowed_targets_json=excluded.allowed_targets_json,
                    allowed_methods_json=excluded.allowed_methods_json,
                    max_value_usd=excluded.max_value_usd,
                    daily_value_usd=excluded.daily_value_usd,
                    max_slippage_bps=excluded.max_slippage_bps,
                    expires_at=excluded.expires_at,
                    require_human_approval=excluded.require_human_approval,
                    revoked=excluded.revoked,
                    updated_at=excluded.updated_at""",
                (
                    policy.policy_id,
                    policy.owner,
                    policy.agent_id,
                    policy.chain_id,
                    json.dumps(list(policy.allowed_targets), sort_keys=True),
                    json.dumps(list(policy.allowed_methods), sort_keys=True),
                    policy.max_value_usd,
                    policy.daily_value_usd,
                    policy.max_slippage_bps,
                    policy.expires_at.isoformat(),
                    int(policy.require_human_approval),
                    int(policy.revoked),
                    now,
                    now,
                ),
            )
        return self.get_policy(policy.policy_id)

    def get_policy(self, policy_id: str) -> PermissionPolicy:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM policies WHERE policy_id=?", (policy_id,)).fetchone()
        if not row:
            raise KeyError(f"policy not found: {policy_id}")
        return self._policy_from_row(row)

    def list_policies(self, *, owner: str | None = None) -> list[PermissionPolicy]:
        with self._connect() as conn:
            if owner:
                rows = conn.execute(
                    "SELECT * FROM policies WHERE lower(owner)=lower(?) ORDER BY created_at DESC",
                    (owner,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM policies ORDER BY created_at DESC").fetchall()
        return [self._policy_from_row(row) for row in rows]

    def create_task(
        self,
        *,
        task_id: str,
        agent_id: str,
        policy_id: str,
        request: Mapping[str, Any],
        idempotency_key: str,
    ) -> TaskRecord:
        with self._lock, self._connect() as conn:
            existing = conn.execute(
                "SELECT task_id FROM idempotency WHERE idempotency_key=?",
                (idempotency_key,),
            ).fetchone()
            if existing:
                raise DuplicateRequestError(
                    f"idempotency key already belongs to task {existing['task_id']}"
                )
            now = self._now()
            conn.execute(
                """INSERT INTO tasks
                (task_id, agent_id, policy_id, state, request_json, created_at, updated_at, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                (
                    task_id,
                    agent_id,
                    policy_id,
                    TaskState.DRAFT.value,
                    json.dumps(dict(request), sort_keys=True),
                    now,
                    now,
                ),
            )
            conn.execute(
                "INSERT INTO idempotency(idempotency_key, task_id, recorded_at) VALUES (?, ?, ?)",
                (idempotency_key, task_id, now),
            )
            conn.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> TaskRecord:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise KeyError(f"task not found: {task_id}")
        return TaskRecord(
            task_id=row["task_id"],
            agent_id=row["agent_id"],
            policy_id=row["policy_id"],
            state=TaskState(row["state"]),
            request=json.loads(row["request_json"]),
            simulation=json.loads(row["simulation_json"]) if row["simulation_json"] else None,
            receipt=json.loads(row["receipt_json"]) if row["receipt_json"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            version=row["version"],
        )

    def list_tasks(self, *, policy_id: str | None = None, limit: int = 100) -> list[TaskRecord]:
        bounded_limit = max(1, min(limit, 500))
        with self._connect() as conn:
            if policy_id:
                rows = conn.execute(
                    "SELECT task_id FROM tasks WHERE policy_id=? ORDER BY created_at DESC LIMIT ?",
                    (policy_id, bounded_limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT task_id FROM tasks ORDER BY created_at DESC LIMIT ?",
                    (bounded_limit,),
                ).fetchall()
        return [self.get_task(str(row["task_id"])) for row in rows]

    def update_task(
        self,
        task_id: str,
        *,
        expected_version: int,
        state: TaskState,
        simulation: Mapping[str, Any] | None = None,
        receipt: Mapping[str, Any] | None = None,
    ) -> TaskRecord:
        with self._lock, self._connect() as conn:
            current = conn.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
            if not current:
                raise KeyError(f"task not found: {task_id}")
            result = conn.execute(
                """UPDATE tasks SET state=?, simulation_json=?, receipt_json=?,
                   updated_at=?, version=version+1 WHERE task_id=? AND version=?""",
                (
                    state.value,
                    json.dumps(dict(simulation), sort_keys=True)
                    if simulation is not None
                    else current["simulation_json"],
                    json.dumps(dict(receipt), sort_keys=True)
                    if receipt is not None
                    else current["receipt_json"],
                    self._now(),
                    task_id,
                    expected_version,
                ),
            )
            if result.rowcount != 1:
                raise RuntimeError("optimistic lock conflict")
        return self.get_task(task_id)

    def has_idempotency(self, key: str) -> bool:
        with self._connect() as conn:
            return (
                conn.execute("SELECT 1 FROM idempotency WHERE idempotency_key=?", (key,)).fetchone()
                is not None
            )

    def spent_today(self, policy_id: str) -> float:
        day = datetime.now(UTC).date().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT spent_usd FROM policy_spend WHERE policy_id=? AND day=?",
                (policy_id, day),
            ).fetchone()
        return float(row["spent_usd"]) if row else 0.0

    def add_spend(self, policy_id: str, value_usd: float) -> None:
        day = datetime.now(UTC).date().isoformat()
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO policy_spend(policy_id, day, spent_usd) VALUES (?, ?, ?)
                   ON CONFLICT(policy_id, day) DO UPDATE SET spent_usd=spent_usd+excluded.spent_usd""",
                (policy_id, day, value_usd),
            )

    def set_flag(self, name: str, value: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO flags(name, value, updated_at) VALUES (?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at""",
                (name, value, self._now()),
            )

    def get_flag(self, name: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM flags WHERE name=?", (name,)).fetchone()
        return str(row["value"]) if row else default

    def save_wallet_challenge(self, *, owner: str, message: str, expires_at: datetime) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO wallet_challenges(owner, message, expires_at, used)
                   VALUES (?, ?, ?, 0)
                   ON CONFLICT(owner) DO UPDATE SET
                     message=excluded.message,
                     expires_at=excluded.expires_at,
                     used=0""",
                (owner.lower(), message, expires_at.isoformat()),
            )

    def get_wallet_challenge(self, owner: str) -> tuple[str, datetime, bool]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT message, expires_at, used FROM wallet_challenges WHERE owner=?",
                (owner.lower(),),
            ).fetchone()
        if not row:
            raise KeyError("wallet challenge not found")
        return (
            str(row["message"]),
            datetime.fromisoformat(str(row["expires_at"])),
            bool(row["used"]),
        )

    def consume_wallet_challenge(self, owner: str) -> None:
        with self._lock, self._connect() as conn:
            result = conn.execute(
                "UPDATE wallet_challenges SET used=1 WHERE owner=? AND used=0",
                (owner.lower(),),
            )
            if result.rowcount != 1:
                raise ValueError("wallet challenge already used or missing")

    def save_wallet_session(self, *, token_hash: str, owner: str, expires_at: datetime) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO wallet_sessions(token_hash, owner, expires_at, created_at)
                   VALUES (?, ?, ?, ?)""",
                (token_hash, owner.lower(), expires_at.isoformat(), self._now()),
            )

    def get_wallet_session(self, token_hash: str) -> tuple[str, datetime]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT owner, expires_at FROM wallet_sessions WHERE token_hash=?",
                (token_hash,),
            ).fetchone()
        if not row:
            raise KeyError("wallet session not found")
        return str(row["owner"]), datetime.fromisoformat(str(row["expires_at"]))
