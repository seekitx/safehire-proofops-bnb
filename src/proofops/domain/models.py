from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentCategory(str, Enum):
    REBALANCING = "rebalancing"
    GRID_TRADING = "grid_trading"
    YIELD_OPTIMISATION = "yield_optimisation"
    HEALTH_FACTOR = "health_factor_monitoring"


class EvidenceLevel(int, Enum):
    SELF_REPORTED = 0
    SIGNED_ENDPOINT = 1
    TESTNET_TRANSACTION = 2
    MAINNET_TRANSACTION = 3
    VERIFIED_TRACK_RECORD = 4


class DataSource(str, Enum):
    LIVE_ONCHAIN = "live_onchain"
    VERIFIED_HISTORICAL = "verified_historical"
    TESTNET_EVIDENCE = "testnet_evidence"
    BENCHMARK_GENERATED = "benchmark_generated"
    DEMO_FIXTURE = "demo_fixture"
    SELF_REPORTED = "self_reported"


class ExecutionMode(str, Enum):
    DEMO = "demo"
    BSC_TESTNET = "bsc_testnet"
    BSC_MAINNET = "bsc_mainnet"


class TaskState(str, Enum):
    DRAFT = "draft"
    SIMULATED = "simulated"
    APPROVAL_REQUIRED = "approval_required"
    APPROVED = "approved"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REVOKED = "revoked"


TERMINAL_TASK_STATES = {TaskState.SUCCEEDED, TaskState.FAILED, TaskState.REVOKED}


@dataclass(frozen=True)
class EvidenceRef:
    evidence_id: str
    level: EvidenceLevel
    source: DataSource
    kind: str
    uri: str | None = None
    tx_hash: str | None = None
    chain_id: int | None = None
    observed_at: datetime = field(default_factory=utc_now)
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["level"] = int(self.level)
        data["source"] = self.source.value
        data["observed_at"] = self.observed_at.isoformat()
        return data


@dataclass(frozen=True)
class AgentMetrics:
    identity: float
    execution_reliability: float
    track_record: float
    risk: float
    cost: float
    benchmark_advantage: float
    freshness: float
    category_metrics: Mapping[str, float | int | str | None] = field(default_factory=dict)

    def validate(self) -> None:
        for name in (
            "identity",
            "execution_reliability",
            "track_record",
            "risk",
            "cost",
            "benchmark_advantage",
            "freshness",
        ):
            value = float(getattr(self, name))
            if value < 0 or value > 100:
                raise ValueError(f"{name} must be in [0, 100], got {value}")


@dataclass(frozen=True)
class AgentDescriptor:
    agent_id: str
    name: str
    category: AgentCategory
    description: str
    endpoint: str
    chain_id: int
    owner: str
    contract_address: str | None
    live_bsc: bool
    metrics: AgentMetrics
    evidence: tuple[EvidenceRef, ...] = ()
    tags: tuple[str, ...] = ()
    version: str = "0.1.0"

    def validate(self) -> None:
        if not self.agent_id or not self.name:
            raise ValueError("agent_id and name are required")
        if self.chain_id not in {56, 97}:
            raise ValueError("SafeHire only lists BSC mainnet/testnet agents")
        if not self.endpoint.startswith(("https://", "http://")):
            raise ValueError("agent endpoint must be HTTP(S)")
        self.metrics.validate()

    @property
    def strongest_evidence_level(self) -> EvidenceLevel:
        if not self.evidence:
            return EvidenceLevel.SELF_REPORTED
        return max((item.level for item in self.evidence), key=int)

    @property
    def has_fixture_evidence(self) -> bool:
        return any(item.source == DataSource.DEMO_FIXTURE for item in self.evidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "category": self.category.value,
            "description": self.description,
            "endpoint": self.endpoint,
            "chain_id": self.chain_id,
            "owner": self.owner,
            "contract_address": self.contract_address,
            "live_bsc": self.live_bsc,
            "metrics": {
                **{k: v for k, v in asdict(self.metrics).items() if k != "category_metrics"},
                "category_metrics": dict(self.metrics.category_metrics),
            },
            "evidence": [item.to_dict() for item in self.evidence],
            "tags": list(self.tags),
            "version": self.version,
        }


@dataclass(frozen=True)
class ProofBreakdown:
    raw_score: float
    final_score: float
    evidence_cap: float
    weighted_components: Mapping[str, float]
    penalties: tuple[str, ...]
    strengths: tuple[str, ...]
    strongest_evidence_level: EvidenceLevel
    source_labels: tuple[DataSource, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_score": self.raw_score,
            "final_score": self.final_score,
            "evidence_cap": self.evidence_cap,
            "weighted_components": dict(self.weighted_components),
            "penalties": list(self.penalties),
            "strengths": list(self.strengths),
            "strongest_evidence_level": int(self.strongest_evidence_level),
            "source_labels": [source.value for source in self.source_labels],
        }


@dataclass(frozen=True)
class PermissionPolicy:
    policy_id: str
    owner: str
    agent_id: str
    chain_id: int
    allowed_targets: tuple[str, ...]
    allowed_methods: tuple[str, ...]
    max_value_usd: float
    daily_value_usd: float
    max_slippage_bps: int
    expires_at: datetime
    require_human_approval: bool = True
    revoked: bool = False

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or utc_now()) >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["expires_at"] = self.expires_at.isoformat()
        data["allowed_targets"] = list(self.allowed_targets)
        data["allowed_methods"] = list(self.allowed_methods)
        return data


@dataclass(frozen=True)
class ExecutionIntent:
    task_id: str
    idempotency_key: str
    agent_id: str
    chain_id: int
    target: str
    method: str
    value_usd: float
    slippage_bps: int
    deadline: datetime
    mode: ExecutionMode
    simulation_passed: bool
    human_approved: bool
    source: DataSource
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["deadline"] = self.deadline.isoformat()
        data["mode"] = self.mode.value
        data["source"] = self.source.value
        data["metadata"] = dict(self.metadata)
        return data


@dataclass(frozen=True)
class RiskDecision:
    allowed: bool
    reasons: tuple[str, ...]
    policy_id: str
    evaluated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reasons": list(self.reasons),
            "policy_id": self.policy_id,
            "evaluated_at": self.evaluated_at.isoformat(),
        }


@dataclass(frozen=True)
class ExecutionReceipt:
    task_id: str
    success: bool
    mode: ExecutionMode
    tx_hash: str | None
    chain_id: int
    gas_used: int | None
    cost_usd: float | None
    source: DataSource
    result: Mapping[str, Any]
    error_code: str | None = None
    error_message: str | None = None
    created_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "success": self.success,
            "mode": self.mode.value,
            "tx_hash": self.tx_hash,
            "chain_id": self.chain_id,
            "gas_used": self.gas_used,
            "cost_usd": self.cost_usd,
            "source": self.source.value,
            "result": dict(self.result),
            "error_code": self.error_code,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class LpPosition:
    current_price: float
    lower_price: float
    upper_price: float
    realized_volatility_30d: float
    fee_apr: float
    liquidity_usd: float
    estimated_rebalance_cost_usd: float
    uncollected_fees_usd: float = 0.0


@dataclass(frozen=True)
class LpSimulation:
    should_rebalance: bool
    current_in_range: bool
    target_lower: float
    target_upper: float
    estimated_benefit_usd: float
    estimated_cost_usd: float
    safety_multiple: float
    confidence: float
    reasons: tuple[str, ...]
    assumptions: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "reasons": list(self.reasons),
            "assumptions": dict(self.assumptions),
        }
