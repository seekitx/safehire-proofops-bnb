from __future__ import annotations

import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from proofops.domain.errors import RiskRejectedError
from proofops.domain.models import (
    DataSource,
    ExecutionIntent,
    ExecutionMode,
    PermissionPolicy,
    TaskState,
)

from .adapters import ExecutionAdapter
from .risk_gate import RiskGate
from .state_machine import require_transition
from .store import SQLiteStore, TaskRecord


class TaskService:
    def __init__(
        self, *, store: SQLiteStore, ledger: Any, risk_gate: RiskGate, adapter: ExecutionAdapter
    ):
        self._store = store
        self._ledger = ledger
        self._risk_gate = risk_gate
        self._adapter = adapter

    def create_policy(
        self,
        *,
        owner: str,
        agent_id: str,
        chain_id: int,
        allowed_targets: tuple[str, ...],
        allowed_methods: tuple[str, ...],
        max_value_usd: float,
        daily_value_usd: float,
        max_slippage_bps: int,
        ttl_minutes: int,
        require_human_approval: bool = True,
    ) -> PermissionPolicy:
        if ttl_minutes <= 0 or ttl_minutes > 24 * 60:
            raise ValueError("ttl_minutes must be in (0, 1440]")
        if not allowed_targets or not allowed_methods:
            raise ValueError("allowlists cannot be empty")
        policy = PermissionPolicy(
            policy_id=f"pol_{uuid.uuid4().hex[:20]}",
            owner=owner,
            agent_id=agent_id,
            chain_id=chain_id,
            allowed_targets=tuple(item.lower() for item in allowed_targets),
            allowed_methods=tuple(item.lower() for item in allowed_methods),
            max_value_usd=max_value_usd,
            daily_value_usd=daily_value_usd,
            max_slippage_bps=max_slippage_bps,
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
            require_human_approval=require_human_approval,
        )
        policy = self._store.save_policy(policy)
        self._ledger.append(
            kind="permission_created", source="task.service", payload=policy.to_dict()
        )
        return policy

    def get_policy(self, policy_id: str) -> PermissionPolicy:
        return self._store.get_policy(policy_id)

    def list_policies(self, *, owner: str | None = None) -> list[PermissionPolicy]:
        return self._store.list_policies(owner=owner)

    def revoke_policy(self, policy_id: str) -> PermissionPolicy:
        current = self.get_policy(policy_id)
        revoked = PermissionPolicy(**{**current.__dict__, "revoked": True})
        revoked = self._store.save_policy(revoked)
        self._ledger.append(
            kind="permission_revoked", source="task.service", payload=revoked.to_dict()
        )
        return revoked

    def create_task(
        self,
        *,
        agent_id: str,
        policy_id: str,
        request: Mapping[str, Any],
        idempotency_key: str,
    ) -> TaskRecord:
        policy = self.get_policy(policy_id)
        if policy.agent_id != agent_id:
            raise ValueError("policy agent_id does not match requested agent")
        task = self._store.create_task(
            task_id=f"task_{uuid.uuid4().hex[:20]}",
            agent_id=agent_id,
            policy_id=policy_id,
            request=request,
            idempotency_key=idempotency_key,
        )
        self._ledger.append(kind="task_created", source="task.service", payload=task.to_dict())
        return task

    def get_task(self, task_id: str) -> TaskRecord:
        return self._store.get_task(task_id)

    def list_tasks(self, *, policy_id: str | None = None, limit: int = 100) -> list[TaskRecord]:
        return self._store.list_tasks(policy_id=policy_id, limit=limit)

    def simulate(self, task_id: str, result: Mapping[str, Any]) -> TaskRecord:
        task = self._store.get_task(task_id)
        require_transition(task.state, TaskState.SIMULATED)
        task = self._store.update_task(
            task_id, expected_version=task.version, state=TaskState.SIMULATED, simulation=result
        )
        require_transition(task.state, TaskState.APPROVAL_REQUIRED)
        task = self._store.update_task(
            task_id, expected_version=task.version, state=TaskState.APPROVAL_REQUIRED
        )
        self._ledger.append(kind="task_simulated", source="task.service", payload=task.to_dict())
        return task

    def approve(self, task_id: str) -> TaskRecord:
        task = self._store.get_task(task_id)
        require_transition(task.state, TaskState.APPROVED)
        task = self._store.update_task(
            task_id, expected_version=task.version, state=TaskState.APPROVED
        )
        self._ledger.append(kind="task_approved", source="task.service", payload=task.to_dict())
        return task

    async def execute(
        self,
        task_id: str,
        *,
        idempotency_key: str,
        chain_id: int,
        target: str,
        method: str,
        value_usd: float,
        slippage_bps: int,
        mode: ExecutionMode,
        source: DataSource,
        metadata: Mapping[str, Any] | None = None,
    ) -> TaskRecord:
        task = self._store.get_task(task_id)
        policy = self.get_policy(task.policy_id)
        intent = ExecutionIntent(
            task_id=task.task_id,
            idempotency_key=idempotency_key,
            agent_id=task.agent_id,
            chain_id=chain_id,
            target=target.lower(),
            method=method.lower(),
            value_usd=value_usd,
            slippage_bps=slippage_bps,
            deadline=datetime.now(UTC) + timedelta(minutes=5),
            mode=mode,
            simulation_passed=bool(task.simulation),
            human_approved=task.state == TaskState.APPROVED,
            source=source,
            metadata={**(metadata or {}), "policy_id": task.policy_id},
        )
        decision = self._risk_gate.evaluate(intent, policy)
        self._ledger.append(
            kind="risk_decision",
            source="risk.gate",
            payload={"intent": intent.to_dict(), "decision": decision.to_dict()},
        )
        if not decision.allowed:
            raise RiskRejectedError(",".join(decision.reasons))

        require_transition(task.state, TaskState.EXECUTING)
        task = self._store.update_task(
            task_id, expected_version=task.version, state=TaskState.EXECUTING
        )
        try:
            receipt = await self._adapter.execute(intent)
            target_state = TaskState.SUCCEEDED if receipt.success else TaskState.FAILED
            task = self._store.update_task(
                task_id,
                expected_version=task.version,
                state=target_state,
                receipt=receipt.to_dict(),
            )
            if receipt.success:
                self._store.add_spend(task.policy_id, value_usd)
        # Adapter boundaries may raise provider-specific exceptions. They are converted
        # into a failed receipt so a task never remains stuck in EXECUTING.
        except Exception as exc:  # noqa: BLE001
            task = self._store.update_task(
                task_id,
                expected_version=task.version,
                state=TaskState.FAILED,
                receipt={"success": False, "error_code": type(exc).__name__, "error": str(exc)},
            )
        self._ledger.append(kind="task_executed", source="task.service", payload=task.to_dict())
        return task

    def revoke_task(self, task_id: str) -> TaskRecord:
        task = self._store.get_task(task_id)
        require_transition(task.state, TaskState.REVOKED)
        task = self._store.update_task(
            task_id, expected_version=task.version, state=TaskState.REVOKED
        )
        self._ledger.append(kind="task_revoked", source="task.service", payload=task.to_dict())
        return task
