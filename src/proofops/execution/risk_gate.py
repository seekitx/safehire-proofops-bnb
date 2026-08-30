from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from proofops.domain.models import (
    DataSource,
    ExecutionIntent,
    ExecutionMode,
    PermissionPolicy,
    RiskDecision,
)


class RiskGate:
    """Deterministic authorization boundary.

    No model, plugin or sponsor adapter can bypass this gate. Its output is fully
    explainable and suitable for unit tests and evidence capture.
    """

    def __init__(
        self,
        *,
        allow_bsc_mainnet: bool = False,
        kill_switch: Callable[[], bool] | None = None,
        spent_today: Callable[[str], float] | None = None,
        idempotency_seen: Callable[[str], bool] | None = None,
    ) -> None:
        self._allow_bsc_mainnet = allow_bsc_mainnet
        self._kill_switch = kill_switch or (lambda: False)
        self._spent_today = spent_today or (lambda _policy_id: 0.0)
        self._idempotency_seen = idempotency_seen or (lambda _key: False)

    def evaluate(self, intent: ExecutionIntent, policy: PermissionPolicy) -> RiskDecision:
        reasons: list[str] = []
        now = datetime.now(UTC)

        if self._kill_switch():
            reasons.append("global_kill_switch_enabled")
        if policy.revoked:
            reasons.append("policy_revoked")
        if policy.is_expired(now):
            reasons.append("policy_expired")
        if intent.deadline <= now:
            reasons.append("intent_deadline_expired")
        if intent.agent_id != policy.agent_id:
            reasons.append("agent_not_authorized")
        if intent.chain_id != policy.chain_id:
            reasons.append("chain_not_authorized")
        if intent.chain_id not in {56, 97}:
            reasons.append("unsupported_chain")
        if intent.chain_id == 56 and not self._allow_bsc_mainnet:
            reasons.append("bsc_mainnet_disabled")
        if intent.target.lower() not in {item.lower() for item in policy.allowed_targets}:
            reasons.append("target_not_allowlisted")
        if intent.method.lower() not in {item.lower() for item in policy.allowed_methods}:
            reasons.append("method_not_allowlisted")
        if intent.value_usd < 0:
            reasons.append("negative_value")
        if intent.value_usd > policy.max_value_usd:
            reasons.append("per_transaction_cap_exceeded")
        if self._spent_today(policy.policy_id) + intent.value_usd > policy.daily_value_usd:
            reasons.append("daily_cap_exceeded")
        if intent.slippage_bps > policy.max_slippage_bps:
            reasons.append("slippage_cap_exceeded")
        if not intent.simulation_passed:
            reasons.append("simulation_required")
        if policy.require_human_approval and not intent.human_approved:
            reasons.append("human_approval_required")
        if not intent.idempotency_key:
            reasons.append("idempotency_key_required")
        elif self._idempotency_seen(intent.idempotency_key):
            reasons.append("duplicate_idempotency_key")
        if intent.source == DataSource.DEMO_FIXTURE and intent.mode != ExecutionMode.DEMO:
            reasons.append("fixture_cannot_execute_onchain")
        if intent.mode == ExecutionMode.BSC_MAINNET and intent.chain_id != 56:
            reasons.append("mode_chain_mismatch")
        if intent.mode == ExecutionMode.BSC_TESTNET and intent.chain_id != 97:
            reasons.append("mode_chain_mismatch")

        return RiskDecision(
            allowed=not reasons,
            reasons=tuple(reasons or ("all_checks_passed",)),
            policy_id=policy.policy_id,
        )
