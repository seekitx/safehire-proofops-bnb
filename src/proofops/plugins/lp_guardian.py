from __future__ import annotations

import math
from dataclasses import dataclass

from proofops.domain.models import LpPosition, LpSimulation
from proofops.harness.contracts import HarnessPlugin, PluginContext


@dataclass(frozen=True)
class LpGuardianPolicy:
    safety_multiple: float = 2.0
    horizon_days: int = 7
    min_width_pct: float = 0.03
    max_width_pct: float = 0.40

    @staticmethod
    def _volatility_bucket(volatility: float) -> float:
        if volatility < 0.25:
            return 0.06
        if volatility < 0.50:
            return 0.12
        if volatility < 0.80:
            return 0.20
        return 0.32

    def simulate(self, position: LpPosition, notional_usd: float) -> LpSimulation:
        if notional_usd <= 0:
            raise ValueError("notional_usd must be positive")
        if not (0 < position.lower_price < position.upper_price):
            raise ValueError("invalid LP range")
        if position.current_price <= 0:
            raise ValueError("current_price must be positive")

        in_range = position.lower_price <= position.current_price <= position.upper_price
        bucket = self._volatility_bucket(position.realized_volatility_30d)
        horizon_factor = math.sqrt(max(self.horizon_days, 1) / 7)
        width_pct = min(self.max_width_pct, max(self.min_width_pct, bucket * horizon_factor))
        target_lower = position.current_price * (1 - width_pct)
        target_upper = position.current_price * (1 + width_pct)

        distance_to_edge = (
            min(
                abs(position.current_price - position.lower_price),
                abs(position.upper_price - position.current_price),
            )
            / position.current_price
        )
        near_edge = in_range and distance_to_edge < width_pct * 0.20

        horizon_fee = notional_usd * max(position.fee_apr, 0) * self.horizon_days / 365
        range_capture_factor = min(1.0, max(0.15, 1.0 - position.realized_volatility_30d * 0.35))
        estimated_benefit = horizon_fee * range_capture_factor + position.uncollected_fees_usd
        estimated_cost = max(position.estimated_rebalance_cost_usd, 0)
        cost_justified = estimated_benefit > estimated_cost * self.safety_multiple
        should_rebalance = (not in_range or near_edge) and cost_justified

        reasons: list[str] = []
        if not in_range:
            reasons.append("Current price is outside the existing liquidity range.")
        elif near_edge:
            reasons.append("Current price is close to a range edge.")
        else:
            reasons.append("Current position has adequate distance from both range edges.")
        if cost_justified:
            reasons.append(
                "Estimated horizon benefit exceeds cost by the configured safety multiple."
            )
        else:
            reasons.append("Estimated benefit does not justify rebalancing cost; hold is safer.")
        reasons.append(
            "Recommendation is deterministic and does not grant execution authority to an LLM."
        )

        confidence = 0.50
        confidence += 0.15 if position.liquidity_usd >= 100_000 else 0
        confidence += 0.15 if position.realized_volatility_30d >= 0 else 0
        confidence += 0.10 if position.fee_apr >= 0 else 0
        confidence = min(0.90, confidence)

        return LpSimulation(
            should_rebalance=should_rebalance,
            current_in_range=in_range,
            target_lower=round(target_lower, 8),
            target_upper=round(target_upper, 8),
            estimated_benefit_usd=round(estimated_benefit, 4),
            estimated_cost_usd=round(estimated_cost, 4),
            safety_multiple=self.safety_multiple,
            confidence=round(confidence, 2),
            reasons=tuple(reasons),
            assumptions={
                "volatility_bucket_width_pct": bucket,
                "horizon_days": self.horizon_days,
                "notional_usd": notional_usd,
                "fee_apr": position.fee_apr,
                "no_profit_guarantee": True,
            },
        )


class LpGuardianPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        policy = LpGuardianPolicy(
            safety_multiple=float(self.manifest.config.get("safety_multiple", 2.0)),
            horizon_days=int(self.manifest.config.get("horizon_days", 7)),
        )
        context.provide("pancake.lp_guardian", policy)
        ledger = context.resolve("evidence.ledger")
        ledger.append(
            kind="policy_loaded",
            source=self.manifest.plugin_id,
            payload={
                "policy": "lp_guardian",
                "safety_multiple": policy.safety_multiple,
                "horizon_days": policy.horizon_days,
            },
        )
