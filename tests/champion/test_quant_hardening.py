import copy
import math

import pytest

from proofops.agents.engines import GridTradingEngine, RebalancingEngine, YieldOptimisationEngine
from proofops.agents.service import EXAMPLE_INPUTS
from proofops.domain.models import AgentCategory
from proofops.services.live_agent_market import _safe_number


@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -float("inf")])
def test_non_numeric_market_signals_are_unknown(value):
    assert _safe_number(value) is None


@pytest.mark.parametrize("field,value", [("levels", 3.7), ("levels", True), ("capital_usd", True), ("current_price", float("nan"))])
def test_grid_bad_input_rejected(field, value):
    payload = copy.deepcopy(EXAMPLE_INPUTS[AgentCategory.GRID_TRADING])
    payload[field] = value
    with pytest.raises(ValueError):
        GridTradingEngine().invoke(payload)


def test_missing_grid_costs_fail_closed():
    result = GridTradingEngine().invoke(copy.deepcopy(EXAMPLE_INPUTS[AgentCategory.GRID_TRADING]))
    assert not result.executable and result.result["round_trip_cost_usd"] is None


@pytest.mark.parametrize("cost,expected", [(0, True), (100, False)])
def test_grid_round_trip_cost_gate(cost, expected):
    payload = copy.deepcopy(EXAMPLE_INPUTS[AgentCategory.GRID_TRADING])
    payload.update(fee_bps_per_side=5, slippage_bps_per_side=5, gas_usd_per_order=cost)
    result = GridTradingEngine().invoke(payload)
    assert result.executable is expected
    assert result.result["drawdown_limit_enforced_onchain"] is False


def test_apy_compounds_instead_of_simple_apr():
    candidate = {"protocol": "a", "gross_apy": 100, "risk_score": 0, "tvl_usd": 1_000_000, "transaction_cost_usd": 0}
    payload = {"capital_usd": 1000, "horizon_days": 30, "candidates": [candidate, {**candidate, "protocol": "b"}]}
    value = YieldOptimisationEngine().invoke(payload).result["ranked_candidates"][0]["estimated_net_yield_usd"]
    assert value == pytest.approx(1000 * (2 ** (30 / 365) - 1), abs=0.0001)
    assert not math.isclose(value, 1000 * 30 / 365)


def test_higher_risk_cannot_improve_a_negative_yield():
    low = {"protocol": "lower-risk", "gross_apy": 0, "risk_score": 0, "tvl_usd": 1_000_000, "transaction_cost_usd": 10}
    high = {**low, "protocol": "higher-risk", "risk_score": 100}
    result = YieldOptimisationEngine().invoke({"capital_usd": 1000, "horizon_days": 30, "candidates": [high, low]})
    assert result.result["best_candidate_protocol"] == "lower-risk"
    assert result.result["selected_protocol"] is None and not result.executable
    assert all(row["risk_adjusted_yield_usd"] <= row["estimated_net_yield_usd"] for row in result.result["ranked_candidates"])


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf")])
def test_lp_fee_input_rejected(value):
    payload = copy.deepcopy(EXAMPLE_INPUTS[AgentCategory.REBALANCING])
    payload["uncollected_fees_usd"] = value
    with pytest.raises(ValueError):
        RebalancingEngine().invoke(payload)
