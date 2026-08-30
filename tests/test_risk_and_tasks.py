from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from proofops.domain.errors import DuplicateRequestError, RiskRejectedError, TaskTransitionError
from proofops.domain.models import DataSource, ExecutionIntent, ExecutionMode, TaskState
from proofops.execution.adapters import DemoExecutionAdapter
from proofops.execution.risk_gate import RiskGate
from proofops.execution.service import TaskService
from proofops.execution.store import SQLiteStore
from proofops.plugins.evidence import EvidenceLedger
from tests.helpers import sample_policy


class RiskGateTests(unittest.TestCase):
    def intent(self, **overrides) -> ExecutionIntent:
        data = {
            "task_id": "task",
            "idempotency_key": "exec-key",
            "agent_id": "agent-test",
            "chain_id": 97,
            "target": "0xtarget",
            "method": "collect",
            "value_usd": 10,
            "slippage_bps": 50,
            "deadline": datetime.now(UTC) + timedelta(minutes=5),
            "mode": ExecutionMode.BSC_TESTNET,
            "simulation_passed": True,
            "human_approved": True,
            "source": DataSource.TESTNET_EVIDENCE,
        }
        data.update(overrides)
        return ExecutionIntent(**data)

    def test_all_checks_pass(self) -> None:
        decision = RiskGate().evaluate(self.intent(), sample_policy())
        self.assertTrue(decision.allowed)

    def test_fixture_cannot_execute_onchain(self) -> None:
        decision = RiskGate().evaluate(self.intent(source=DataSource.DEMO_FIXTURE), sample_policy())
        self.assertFalse(decision.allowed)
        self.assertIn("fixture_cannot_execute_onchain", decision.reasons)

    def test_slippage_and_spend_are_blocked(self) -> None:
        decision = RiskGate(spent_today=lambda _p: 495).evaluate(
            self.intent(value_usd=20, slippage_bps=200), sample_policy()
        )
        self.assertIn("daily_cap_exceeded", decision.reasons)
        self.assertIn("slippage_cap_exceeded", decision.reasons)

    def test_mainnet_disabled_by_default(self) -> None:
        decision = RiskGate().evaluate(
            self.intent(chain_id=56, mode=ExecutionMode.BSC_MAINNET),
            sample_policy(chain_id=56),
        )
        self.assertIn("bsc_mainnet_disabled", decision.reasons)


class TaskServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.store = SQLiteStore(Path(self.tmp.name) / "state.db")
        self.ledger = EvidenceLedger(Path(self.tmp.name) / "evidence.jsonl")
        self.service = TaskService(
            store=self.store,
            ledger=self.ledger,
            risk_gate=RiskGate(spent_today=self.store.spent_today),
            adapter=DemoExecutionAdapter(),
        )
        self.policy = self.service.create_policy(
            owner="0xowner",
            agent_id="agent-test",
            chain_id=97,
            allowed_targets=("0xtarget",),
            allowed_methods=("collect",),
            max_value_usd=100,
            daily_value_usd=500,
            max_slippage_bps=100,
            ttl_minutes=60,
        )

    async def asyncTearDown(self) -> None:
        self.tmp.cleanup()

    def create(self, key="create-key-1"):
        return self.service.create_task(
            agent_id="agent-test",
            policy_id=self.policy.policy_id,
            request={"job": "collect"},
            idempotency_key=key,
        )

    async def test_happy_path_state_machine_and_demo_receipt(self) -> None:
        task = self.create()
        self.assertEqual(task.state, TaskState.DRAFT)
        task = self.service.simulate(task.task_id, {"passed": True})
        self.assertEqual(task.state, TaskState.APPROVAL_REQUIRED)
        task = self.service.approve(task.task_id)
        self.assertEqual(task.state, TaskState.APPROVED)
        task = await self.service.execute(
            task.task_id,
            idempotency_key="execute-key-1",
            chain_id=97,
            target="0xtarget",
            method="collect",
            value_usd=1,
            slippage_bps=10,
            mode=ExecutionMode.DEMO,
            source=DataSource.DEMO_FIXTURE,
        )
        self.assertEqual(task.state, TaskState.SUCCEEDED)
        self.assertEqual(task.receipt["source"], DataSource.DEMO_FIXTURE.value)

    async def test_duplicate_create_is_rejected(self) -> None:
        self.create("same-key")
        with self.assertRaises(DuplicateRequestError):
            self.create("same-key")

    async def test_execute_before_approval_is_rejected(self) -> None:
        task = self.create()
        with self.assertRaises(RiskRejectedError):
            await self.service.execute(
                task.task_id,
                idempotency_key="execute-key-2",
                chain_id=97,
                target="0xtarget",
                method="collect",
                value_usd=1,
                slippage_bps=10,
                mode=ExecutionMode.DEMO,
                source=DataSource.DEMO_FIXTURE,
            )

    async def test_invalid_transition_is_rejected(self) -> None:
        task = self.create()
        with self.assertRaises(TaskTransitionError):
            self.service.approve(task.task_id)

    async def test_revoke_policy_blocks_execution(self) -> None:
        task = self.create()
        self.service.simulate(task.task_id, {"passed": True})
        self.service.approve(task.task_id)
        self.service.revoke_policy(self.policy.policy_id)
        with self.assertRaises(RiskRejectedError):
            await self.service.execute(
                task.task_id,
                idempotency_key="execute-key-3",
                chain_id=97,
                target="0xtarget",
                method="collect",
                value_usd=1,
                slippage_bps=10,
                mode=ExecutionMode.DEMO,
                source=DataSource.DEMO_FIXTURE,
            )
