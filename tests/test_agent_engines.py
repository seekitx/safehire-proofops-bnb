from __future__ import annotations

import pytest

from proofops.agents.engines import (
    GridTradingEngine,
    HealthFactorEngine,
    RebalancingEngine,
    YieldOptimisationEngine,
)
from proofops.agents.service import EXAMPLE_INPUTS
from proofops.domain.models import AgentCategory


@pytest.mark.parametrize(
    ("engine", "category"),
    [
        (RebalancingEngine(), AgentCategory.REBALANCING),
        (GridTradingEngine(), AgentCategory.GRID_TRADING),
        (YieldOptimisationEngine(), AgentCategory.YIELD_OPTIMISATION),
        (HealthFactorEngine(), AgentCategory.HEALTH_FACTOR),
    ],
)
def test_each_agent_engine_is_callable_and_labels_its_source(engine, category) -> None:
    result = engine.invoke(dict(EXAMPLE_INPUTS[category]))

    assert result.category is category
    assert 0 <= result.confidence <= 1
    assert "execution_requires_scoped_permission" in result.risk_checks
    assert result.source_labels == ("caller_supplied",)


def test_grid_engine_rejects_price_outside_range() -> None:
    payload = dict(EXAMPLE_INPUTS[AgentCategory.GRID_TRADING])
    payload["current_price"] = payload["upper_price"]

    with pytest.raises(ValueError, match="lower_price < current_price"):
        GridTradingEngine().invoke(payload)


def test_yield_engine_deducts_cost_and_penalizes_risk() -> None:
    result = YieldOptimisationEngine().invoke(
        dict(EXAMPLE_INPUTS[AgentCategory.YIELD_OPTIMISATION])
    )

    ranked = result.result["ranked_candidates"]
    assert len(ranked) == 2
    assert all(
        item["risk_adjusted_yield_usd"] <= item["estimated_net_yield_usd"] for item in ranked
    )
    assert result.result["no_profit_guarantee"] is True


def test_health_factor_engine_recommends_repay_when_below_alert() -> None:
    result = HealthFactorEngine().invoke(dict(EXAMPLE_INPUTS[AgentCategory.HEALTH_FACTOR]))

    assert result.action == "repay_or_add_collateral"
    assert result.executable is True
    assert result.result["repay_to_target_usd"] > 0
