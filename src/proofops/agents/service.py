from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from proofops.agents.engines import ENGINE_BY_CATEGORY, EngineResult
from proofops.domain.models import AgentCategory

EXAMPLE_INPUTS: dict[AgentCategory, dict[str, Any]] = {
    AgentCategory.REBALANCING: {
        "current_price": 620,
        "lower_price": 570,
        "upper_price": 610,
        "realized_volatility_30d": 0.42,
        "fee_apr": 0.18,
        "liquidity_usd": 2_500_000,
        "estimated_rebalance_cost_usd": 0.35,
        "uncollected_fees_usd": 1.2,
        "notional_usd": 1000,
        "source": "caller_supplied",
    },
    AgentCategory.GRID_TRADING: {
        "current_price": 620,
        "lower_price": 560,
        "upper_price": 680,
        "levels": 8,
        "capital_usd": 1000,
        "max_drawdown_pct": 8,
        "source": "caller_supplied",
    },
    AgentCategory.YIELD_OPTIMISATION: {
        "capital_usd": 1000,
        "horizon_days": 30,
        "candidates": [
            {
                "protocol": "PancakeSwap",
                "gross_apy": 11.2,
                "risk_score": 36,
                "tvl_usd": 125_000_000,
                "transaction_cost_usd": 0.35,
            },
            {
                "protocol": "Venus",
                "gross_apy": 8.4,
                "risk_score": 28,
                "tvl_usd": 450_000_000,
                "transaction_cost_usd": 0.22,
            },
        ],
        "source": "caller_supplied",
    },
    AgentCategory.HEALTH_FACTOR: {
        "collateral_usd": 1500,
        "debt_usd": 1000,
        "liquidation_threshold": 0.8,
        "alert_health_factor": 1.25,
        "target_health_factor": 1.5,
        "source": "caller_supplied",
    },
}


class AgentInvocationService:
    def __init__(self, *, registry: Any, ledger: Any) -> None:
        self._registry = registry
        self._ledger = ledger
        self._engines = {
            category: engine_type() for category, engine_type in ENGINE_BY_CATEGORY.items()
        }

    def card(self, agent_id: str) -> dict[str, Any]:
        descriptor = self._registry.get(agent_id)
        return {
            "protocol_version": "proofops-agent/1.0",
            "agent_id": descriptor.agent_id,
            "name": descriptor.name,
            "description": descriptor.description,
            "category": descriptor.category.value,
            "endpoint": descriptor.endpoint,
            "chain_id": descriptor.chain_id,
            "live_bsc": descriptor.live_bsc,
            "contract_address": descriptor.contract_address,
            "methods": {
                "card": f"GET {descriptor.endpoint}",
                "invoke": f"POST {descriptor.endpoint}",
            },
            "example_input": EXAMPLE_INPUTS[descriptor.category],
            "safety": {
                "recommendation_is_deterministic": True,
                "fund_execution_requires_scoped_permission": True,
                "mainnet_disabled_by_default": True,
            },
        }

    def invoke(self, agent_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        descriptor = self._registry.get(agent_id)
        engine = self._engines[descriptor.category]
        result: EngineResult = engine.invoke(payload)
        response = {
            "invocation_id": f"inv_{datetime.now(UTC).strftime('%Y%m%d%H%M%S%f')}",
            "agent_id": descriptor.agent_id,
            "agent_version": descriptor.version,
            "observed_at": datetime.now(UTC).isoformat(),
            **result.to_dict(),
        }
        self._ledger.append(
            kind="agent_invoked",
            source=f"agent.{descriptor.agent_id}",
            payload={
                "agent_id": descriptor.agent_id,
                "invocation_id": response["invocation_id"],
                "action": result.action,
                "executable": result.executable,
                "source_labels": list(result.source_labels),
            },
        )
        return response
