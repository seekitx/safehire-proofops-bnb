from __future__ import annotations

from .models import AgentCategory

REQUIRED_CATEGORY_METRICS: dict[AgentCategory, tuple[str, ...]] = {
    AgentCategory.REBALANCING: (
        "net_apr",
        "in_range_ratio",
        "rebalance_count",
        "fee_earned_usd",
        "impermanent_loss_pct",
        "max_drawdown_pct",
        "average_execution_cost_usd",
    ),
    AgentCategory.GRID_TRADING: (
        "return_7d_pct",
        "return_30d_pct",
        "win_rate",
        "max_drawdown_pct",
        "trades",
        "average_slippage_bps",
        "turnover_usd",
        "track_record_days",
    ),
    AgentCategory.YIELD_OPTIMISATION: (
        "net_apy",
        "yield_stability",
        "protocol_exposure_count",
        "reallocation_cost_usd",
        "tvl_context_usd",
        "risk_tier",
    ),
    AgentCategory.HEALTH_FACTOR: (
        "minimum_health_factor",
        "alert_latency_seconds",
        "response_latency_seconds",
        "uptime_pct",
        "failed_actions",
        "liquidations_prevented",
        "capital_used_usd",
    ),
}


def missing_category_metrics(
    category: AgentCategory, metrics: dict[str, object]
) -> tuple[str, ...]:
    required = REQUIRED_CATEGORY_METRICS[category]
    return tuple(name for name in required if name not in metrics or metrics[name] is None)


def validate_category_metrics(category: AgentCategory, metrics: dict[str, object]) -> None:
    missing = missing_category_metrics(category, metrics)
    if missing:
        raise ValueError(f"missing {category.value} metrics: {', '.join(missing)}")
