from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from proofops.domain.models import AgentCategory, LpPosition
from proofops.plugins.lp_guardian import LpGuardianPolicy


def _number(payload: dict[str, Any], key: str, *, minimum: float | None = None) -> float:
    if key not in payload:
        raise ValueError(f"{key} is required")
    try:
        value = float(payload[key])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a number") from exc
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    if minimum is not None and value < minimum:
        raise ValueError(f"{key} must be at least {minimum}")
    return value


def _integer(payload: dict[str, Any], key: str, *, minimum: int, maximum: int) -> int:
    value = int(_number(payload, key, minimum=float(minimum)))
    if value > maximum:
        raise ValueError(f"{key} must be at most {maximum}")
    return value


@dataclass(frozen=True)
class EngineResult:
    category: AgentCategory
    action: str
    executable: bool
    confidence: float
    result: dict[str, Any]
    risk_checks: tuple[str, ...]
    source_labels: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "action": self.action,
            "executable": self.executable,
            "confidence": self.confidence,
            "result": self.result,
            "risk_checks": list(self.risk_checks),
            "source_labels": list(self.source_labels),
        }


class RebalancingEngine:
    category = AgentCategory.REBALANCING

    def __init__(self, policy: LpGuardianPolicy | None = None) -> None:
        self._policy = policy or LpGuardianPolicy()

    def invoke(self, payload: dict[str, Any]) -> EngineResult:
        position = LpPosition(
            current_price=_number(payload, "current_price", minimum=0.00000001),
            lower_price=_number(payload, "lower_price", minimum=0.00000001),
            upper_price=_number(payload, "upper_price", minimum=0.00000001),
            realized_volatility_30d=_number(payload, "realized_volatility_30d", minimum=0),
            fee_apr=_number(payload, "fee_apr", minimum=0),
            liquidity_usd=_number(payload, "liquidity_usd", minimum=0),
            estimated_rebalance_cost_usd=_number(
                payload, "estimated_rebalance_cost_usd", minimum=0
            ),
            uncollected_fees_usd=float(payload.get("uncollected_fees_usd", 0)),
        )
        simulation = self._policy.simulate(position, _number(payload, "notional_usd", minimum=0.01))
        return EngineResult(
            category=self.category,
            action="rebalance" if simulation.should_rebalance else "hold",
            executable=simulation.should_rebalance,
            confidence=simulation.confidence,
            result=simulation.to_dict(),
            risk_checks=(
                "range_validated",
                "cost_benefit_threshold_enforced",
                "execution_requires_scoped_permission",
            ),
            source_labels=(str(payload.get("source", "caller_supplied")),),
        )


class GridTradingEngine:
    category = AgentCategory.GRID_TRADING

    def invoke(self, payload: dict[str, Any]) -> EngineResult:
        current = _number(payload, "current_price", minimum=0.00000001)
        lower = _number(payload, "lower_price", minimum=0.00000001)
        upper = _number(payload, "upper_price", minimum=0.00000001)
        if not lower < current < upper:
            raise ValueError("lower_price < current_price < upper_price is required")
        levels = _integer(payload, "levels", minimum=2, maximum=50)
        capital = _number(payload, "capital_usd", minimum=1)
        max_drawdown = _number(payload, "max_drawdown_pct", minimum=0)
        if max_drawdown > 50:
            raise ValueError("max_drawdown_pct must be at most 50")
        ratio = (upper / lower) ** (1 / (levels - 1))
        prices = [round(lower * ratio**index, 8) for index in range(levels)]
        per_order = round(capital / levels, 2)
        distance_pct = round((upper - lower) / current * 100, 4)
        return EngineResult(
            category=self.category,
            action="propose_grid",
            executable=True,
            confidence=0.78 if levels <= 20 else 0.68,
            result={
                "grid_prices": prices,
                "capital_per_order_usd": per_order,
                "configured_max_drawdown_pct": max_drawdown,
                "range_width_pct": distance_pct,
                "orders": levels,
                "no_profit_guarantee": True,
            },
            risk_checks=(
                "price_inside_range",
                "order_count_capped",
                "drawdown_budget_capped",
                "execution_requires_scoped_permission",
            ),
            source_labels=(str(payload.get("source", "caller_supplied")),),
        )


class YieldOptimisationEngine:
    category = AgentCategory.YIELD_OPTIMISATION

    def invoke(self, payload: dict[str, Any]) -> EngineResult:
        raw_candidates = payload.get("candidates")
        if not isinstance(raw_candidates, list) or len(raw_candidates) < 2:
            raise ValueError("candidates must contain at least two protocols")
        capital = _number(payload, "capital_usd", minimum=1)
        horizon_days = _integer(payload, "horizon_days", minimum=1, maximum=365)
        ranked: list[dict[str, Any]] = []
        for raw in raw_candidates:
            if not isinstance(raw, dict):
                # Public API validation errors share one stable 422 handler.
                raise ValueError("each candidate must be an object")  # noqa: TRY004
            name = str(raw.get("protocol", "")).strip()
            if not name:
                raise ValueError("candidate protocol is required")
            gross_apy = _number(raw, "gross_apy", minimum=0)
            risk_score = _number(raw, "risk_score", minimum=0)
            if risk_score > 100:
                raise ValueError("risk_score must be at most 100")
            tvl_usd = _number(raw, "tvl_usd", minimum=0)
            transaction_cost_usd = _number(raw, "transaction_cost_usd", minimum=0)
            horizon_yield = capital * gross_apy / 100 * horizon_days / 365
            net_yield = horizon_yield - transaction_cost_usd
            risk_adjusted = net_yield * (1 - risk_score / 125)
            ranked.append(
                {
                    "protocol": name,
                    "gross_apy": gross_apy,
                    "risk_score": risk_score,
                    "tvl_usd": tvl_usd,
                    "transaction_cost_usd": transaction_cost_usd,
                    "estimated_net_yield_usd": round(net_yield, 4),
                    "risk_adjusted_yield_usd": round(risk_adjusted, 4),
                }
            )
        ranked.sort(key=lambda item: float(item["risk_adjusted_yield_usd"]), reverse=True)
        winner = ranked[0]
        return EngineResult(
            category=self.category,
            action="route_to_best_risk_adjusted_yield",
            executable=float(winner["estimated_net_yield_usd"]) > 0,
            confidence=0.8 if float(winner["tvl_usd"]) >= 1_000_000 else 0.62,
            result={
                "selected_protocol": winner["protocol"],
                "ranked_candidates": ranked,
                "capital_usd": capital,
                "horizon_days": horizon_days,
                "no_profit_guarantee": True,
            },
            risk_checks=(
                "transaction_cost_deducted",
                "risk_score_penalized",
                "minimum_two_candidates",
                "execution_requires_scoped_permission",
            ),
            source_labels=(str(payload.get("source", "caller_supplied")),),
        )


class HealthFactorEngine:
    category = AgentCategory.HEALTH_FACTOR

    def invoke(self, payload: dict[str, Any]) -> EngineResult:
        collateral = _number(payload, "collateral_usd", minimum=0)
        debt = _number(payload, "debt_usd", minimum=0.00000001)
        threshold = _number(payload, "liquidation_threshold", minimum=0.01)
        if threshold > 1:
            raise ValueError("liquidation_threshold must be in (0, 1]")
        alert_at = _number(payload, "alert_health_factor", minimum=1)
        target = _number(payload, "target_health_factor", minimum=alert_at)
        health_factor = collateral * threshold / debt
        safe_debt = collateral * threshold / target
        repay = max(0.0, debt - safe_debt)
        action = "repay_or_add_collateral" if health_factor < alert_at else "monitor"
        return EngineResult(
            category=self.category,
            action=action,
            executable=health_factor < alert_at,
            confidence=0.9,
            result={
                "health_factor": round(health_factor, 6),
                "alert_health_factor": alert_at,
                "target_health_factor": target,
                "repay_to_target_usd": round(repay, 4),
                "status": "at_risk" if health_factor < alert_at else "healthy",
                "no_liquidation_prevention_guarantee": True,
            },
            risk_checks=(
                "positive_debt",
                "liquidation_threshold_validated",
                "target_above_alert",
                "execution_requires_scoped_permission",
            ),
            source_labels=(str(payload.get("source", "caller_supplied")),),
        )


ENGINE_BY_CATEGORY = {
    AgentCategory.REBALANCING: RebalancingEngine,
    AgentCategory.GRID_TRADING: GridTradingEngine,
    AgentCategory.YIELD_OPTIMISATION: YieldOptimisationEngine,
    AgentCategory.HEALTH_FACTOR: HealthFactorEngine,
}
