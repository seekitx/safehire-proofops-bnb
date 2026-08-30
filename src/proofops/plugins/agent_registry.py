from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from proofops.domain.category_metrics import validate_category_metrics
from proofops.domain.models import (
    AgentCategory,
    AgentDescriptor,
    AgentMetrics,
    DataSource,
    EvidenceLevel,
    EvidenceRef,
)
from proofops.harness.contracts import HarnessPlugin, PluginContext


class AgentRegistry:
    def __init__(self, agents: list[AgentDescriptor]) -> None:
        self._agents = {agent.agent_id: agent for agent in agents}
        if len(self._agents) != len(agents):
            raise ValueError("duplicate agent_id")
        for agent in agents:
            agent.validate()
            validate_category_metrics(agent.category, dict(agent.metrics.category_metrics))

    @classmethod
    def from_json(
        cls,
        path: str | Path,
        *,
        public_base_url: str = "http://localhost:8000",
    ) -> AgentRegistry:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        agents: list[AgentDescriptor] = []
        for item in raw.get("agents", []):
            metric_data = item["metrics"]
            evidence = []
            for ev in item.get("evidence", []):
                observed_at = ev.get("observed_at")
                evidence.append(
                    EvidenceRef(
                        evidence_id=ev["evidence_id"],
                        level=EvidenceLevel(int(ev["level"])),
                        source=DataSource(ev["source"]),
                        kind=ev["kind"],
                        uri=ev.get("uri"),
                        tx_hash=ev.get("tx_hash"),
                        chain_id=ev.get("chain_id"),
                        observed_at=datetime.fromisoformat(observed_at)
                        if observed_at
                        else datetime.now(UTC),
                        summary=ev.get("summary", ""),
                    )
                )
            agents.append(
                AgentDescriptor(
                    agent_id=item["agent_id"],
                    name=item["name"],
                    category=AgentCategory(item["category"]),
                    description=item["description"],
                    endpoint=str(item["endpoint"]).replace(
                        "{PUBLIC_BASE_URL}", public_base_url.rstrip("/")
                    ),
                    chain_id=int(item["chain_id"]),
                    owner=item["owner"],
                    contract_address=item.get("contract_address"),
                    live_bsc=bool(item.get("live_bsc", False)),
                    metrics=AgentMetrics(
                        identity=float(metric_data["identity"]),
                        execution_reliability=float(metric_data["execution_reliability"]),
                        track_record=float(metric_data["track_record"]),
                        risk=float(metric_data["risk"]),
                        cost=float(metric_data["cost"]),
                        benchmark_advantage=float(metric_data["benchmark_advantage"]),
                        freshness=float(metric_data["freshness"]),
                        category_metrics=dict(metric_data["category_metrics"]),
                    ),
                    evidence=tuple(evidence),
                    tags=tuple(item.get("tags", [])),
                    version=item.get("version", "0.1.0"),
                )
            )
        return cls(agents)

    def list(self, category: AgentCategory | None = None) -> list[AgentDescriptor]:
        agents = list(self._agents.values())
        if category:
            agents = [agent for agent in agents if agent.category == category]
        return sorted(agents, key=lambda item: (item.category.value, item.name))

    def get(self, agent_id: str) -> AgentDescriptor:
        try:
            return self._agents[agent_id]
        except KeyError as exc:
            raise KeyError(f"agent not found: {agent_id}") from exc

    def replace(self, agent: AgentDescriptor) -> None:
        agent.validate()
        validate_category_metrics(agent.category, dict(agent.metrics.category_metrics))
        self._agents[agent.agent_id] = agent

    def category_counts(self) -> dict[str, int]:
        result = {category.value: 0 for category in AgentCategory}
        for agent in self._agents.values():
            result[agent.category.value] += 1
        return result


class AgentRegistryPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        path = self.manifest.config.get("path", "config/agents.json")
        registry = AgentRegistry.from_json(
            path,
            public_base_url=str(
                self.manifest.config.get("public_base_url", "http://localhost:8000")
            ),
        )
        context.provide("agents.registry", registry)
        ledger = context.resolve("evidence.ledger")
        ledger.append(
            kind="agent_registry_loaded",
            source=self.manifest.plugin_id,
            payload={"count": len(registry.list()), "categories": registry.category_counts()},
        )
