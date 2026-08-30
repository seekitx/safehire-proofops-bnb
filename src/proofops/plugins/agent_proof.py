from __future__ import annotations

from typing import ClassVar

from proofops.domain.category_metrics import missing_category_metrics
from proofops.domain.models import (
    AgentDescriptor,
    DataSource,
    EvidenceLevel,
    ProofBreakdown,
)
from proofops.harness.contracts import HarnessPlugin, PluginContext


class AgentProofScorer:
    WEIGHTS: ClassVar[dict[str, float]] = {
        "identity": 0.10,
        "execution_reliability": 0.20,
        "track_record": 0.15,
        "risk": 0.20,
        "cost": 0.10,
        "benchmark_advantage": 0.15,
        "freshness": 0.10,
    }
    CAPS: ClassVar[dict[EvidenceLevel, float]] = {
        EvidenceLevel.SELF_REPORTED: 35.0,
        EvidenceLevel.SIGNED_ENDPOINT: 55.0,
        EvidenceLevel.TESTNET_TRANSACTION: 75.0,
        EvidenceLevel.MAINNET_TRANSACTION: 90.0,
        EvidenceLevel.VERIFIED_TRACK_RECORD: 100.0,
    }

    def score(self, agent: AgentDescriptor) -> ProofBreakdown:
        agent.metrics.validate()
        components: dict[str, float] = {}
        for field_name, weight in self.WEIGHTS.items():
            components[field_name] = round(float(getattr(agent.metrics, field_name)) * weight, 3)
        raw_score = round(sum(components.values()), 2)
        strongest = agent.strongest_evidence_level
        cap = self.CAPS[strongest]
        penalties: list[str] = []
        strengths: list[str] = []

        sources = tuple(
            sorted({item.source for item in agent.evidence}, key=lambda item: item.value)
        )
        if not agent.evidence:
            penalties.append("No evidence references; score capped as self-reported.")
        if DataSource.DEMO_FIXTURE in sources:
            cap = min(cap, 30.0)
            penalties.append("Demo fixture evidence can never produce a production-grade score.")
        if not agent.live_bsc:
            cap = min(cap, 50.0)
            penalties.append("Agent is not marked live on BSC.")
        if not agent.contract_address:
            cap = min(cap, 60.0)
            penalties.append("No onchain agent/registry contract address.")
        missing = missing_category_metrics(agent.category, dict(agent.metrics.category_metrics))
        if missing:
            cap = min(cap, 45.0)
            penalties.append(f"Missing category metrics: {', '.join(missing)}")
        if agent.metrics.execution_reliability >= 85:
            strengths.append("High execution reliability evidence.")
        if agent.metrics.risk >= 85:
            strengths.append("Strong deterministic risk controls.")
        if strongest >= EvidenceLevel.MAINNET_TRANSACTION:
            strengths.append("Onchain mainnet execution evidence present.")
        if strongest == EvidenceLevel.VERIFIED_TRACK_RECORD:
            strengths.append("Multi-day verified track record present.")

        final_score = round(min(raw_score, cap), 2)
        return ProofBreakdown(
            raw_score=raw_score,
            final_score=final_score,
            evidence_cap=cap,
            weighted_components=components,
            penalties=tuple(penalties),
            strengths=tuple(strengths),
            strongest_evidence_level=strongest,
            source_labels=sources,
        )


class AgentProofPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        context.provide("agents.proof", AgentProofScorer())
