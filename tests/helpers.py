from __future__ import annotations

from datetime import UTC, datetime, timedelta

from proofops.domain.models import (
    AgentCategory,
    AgentDescriptor,
    AgentMetrics,
    DataSource,
    EvidenceLevel,
    EvidenceRef,
    PermissionPolicy,
)


def sample_agent(
    *,
    source: DataSource = DataSource.TESTNET_EVIDENCE,
    level: EvidenceLevel = EvidenceLevel.TESTNET_TRANSACTION,
    live: bool = True,
    contract: str | None = "0x1111111111111111111111111111111111111111",
) -> AgentDescriptor:
    return AgentDescriptor(
        agent_id="agent-test",
        name="Test Agent",
        category=AgentCategory.REBALANCING,
        description="test",
        endpoint="https://agent.example",
        chain_id=97,
        owner="0x2222222222222222222222222222222222222222",
        contract_address=contract,
        live_bsc=live,
        metrics=AgentMetrics(
            identity=90,
            execution_reliability=95,
            track_record=85,
            risk=92,
            cost=88,
            benchmark_advantage=90,
            freshness=95,
            category_metrics={
                "net_apr": 20.0,
                "in_range_ratio": 0.91,
                "rebalance_count": 10,
                "fee_earned_usd": 100,
                "impermanent_loss_pct": -1.5,
                "max_drawdown_pct": -2.0,
                "average_execution_cost_usd": 0.2,
            },
        ),
        evidence=(
            EvidenceRef(
                evidence_id="ev-test",
                level=level,
                source=source,
                kind="transaction",
                tx_hash="0xabc",
                chain_id=97,
            ),
        ),
    )


def sample_policy(**overrides) -> PermissionPolicy:
    data = {
        "policy_id": "pol-test",
        "owner": "0xowner",
        "agent_id": "agent-test",
        "chain_id": 97,
        "allowed_targets": ("0xtarget",),
        "allowed_methods": ("collect",),
        "max_value_usd": 100.0,
        "daily_value_usd": 500.0,
        "max_slippage_bps": 100,
        "expires_at": datetime.now(UTC) + timedelta(hours=1),
        "require_human_approval": True,
        "revoked": False,
    }
    data.update(overrides)
    return PermissionPolicy(**data)
