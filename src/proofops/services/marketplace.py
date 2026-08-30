from __future__ import annotations

from typing import Any

from proofops.domain.models import AgentCategory


class MarketplaceService:
    def __init__(self, registry: Any, scorer: Any) -> None:
        self._registry = registry
        self._scorer = scorer

    def list_agents(self, category: str | None = None) -> list[dict[str, Any]]:
        parsed = AgentCategory(category) if category else None
        result: list[dict[str, Any]] = []
        for agent in self._registry.list(parsed):
            proof = self._scorer.score(agent)
            result.append({**agent.to_dict(), "agent_proof": proof.to_dict()})
        return result

    def get_agent(self, agent_id: str) -> dict[str, Any]:
        agent = self._registry.get(agent_id)
        return {**agent.to_dict(), "agent_proof": self._scorer.score(agent).to_dict()}

    def compare(self, agent_ids: list[str]) -> dict[str, Any]:
        if len(agent_ids) < 2 or len(agent_ids) > 3:
            raise ValueError("compare requires two or three agents")
        if len(set(agent_ids)) != len(agent_ids):
            raise ValueError("agent_ids must be unique")
        agents = [self._registry.get(agent_id) for agent_id in agent_ids]
        return {
            "agents": [
                {**agent.to_dict(), "agent_proof": self._scorer.score(agent).to_dict()}
                for agent in agents
            ],
            "comparison_note": (
                "Different agent categories use different job-specific metrics. "
                "AgentProof is a common trust layer, not a claim that unlike strategies are interchangeable."
            ),
        }
