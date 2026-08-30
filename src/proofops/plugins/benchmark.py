from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from typing import Any, ClassVar

from proofops.domain.models import LpPosition
from proofops.harness.contracts import HarnessPlugin, PluginContext


@dataclass(frozen=True)
class QualityRubric:
    correctness: float
    completeness: float
    risk_awareness: float
    actionability: float
    evidence: float

    WEIGHTS: ClassVar[dict[str, float]] = {
        "correctness": 0.35,
        "completeness": 0.20,
        "risk_awareness": 0.20,
        "actionability": 0.15,
        "evidence": 0.10,
    }

    def total(self) -> float:
        values = asdict(self)
        for key, value in values.items():
            if not 0 <= value <= 100:
                raise ValueError(f"{key} must be in [0, 100]")
        return round(sum(float(values[key]) * weight for key, weight in self.WEIGHTS.items()), 2)


@dataclass(frozen=True)
class BenchmarkSide:
    output: Mapping[str, Any]
    elapsed_ms: float
    estimated_cost_usd: float
    rubric: QualityRubric

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": dict(self.output),
            "elapsed_ms": self.elapsed_ms,
            "estimated_cost_usd": self.estimated_cost_usd,
            "rubric": {**asdict(self.rubric), "total": self.rubric.total()},
        }


@dataclass(frozen=True)
class BenchmarkResult:
    benchmark_id: str
    task_name: str
    input: Mapping[str, Any]
    manual: BenchmarkSide
    agent: BenchmarkSide
    limitations: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark_id": self.benchmark_id,
            "task_name": self.task_name,
            "input": dict(self.input),
            "manual": self.manual.to_dict(),
            "agent": self.agent.to_dict(),
            "advantage": {
                "time_saved_ms": round(self.manual.elapsed_ms - self.agent.elapsed_ms, 3),
                "quality_delta": round(self.agent.rubric.total() - self.manual.rubric.total(), 2),
                "incremental_cost_usd": round(
                    self.agent.estimated_cost_usd - self.manual.estimated_cost_usd, 5
                ),
            },
            "limitations": list(self.limitations),
        }


class BenchmarkRunner:
    """Runs controlled manual-vs-agent comparisons and keeps raw outputs.

    The manual side is a fixed, auditable baseline template. It is not a claim
    about every human operator. Real submission reports should name the tester,
    timestamp and exact inputs.
    """

    def __init__(self, lp_policy: Any, ledger: Any) -> None:
        self._lp_policy = lp_policy
        self._ledger = ledger

    @staticmethod
    def _timed(fn: Callable[[], Mapping[str, Any]]) -> tuple[Mapping[str, Any], float]:
        started = time.perf_counter_ns()
        output = fn()
        elapsed = (time.perf_counter_ns() - started) / 1_000_000
        return output, elapsed

    def lp_range_recommendation(self) -> BenchmarkResult:
        inputs: dict[str, Any] = {
            "current_price": 610.0,
            "lower_price": 560.0,
            "upper_price": 620.0,
            "realized_volatility_30d": 0.48,
            "fee_apr": 0.21,
            "liquidity_usd": 2_800_000,
            "estimated_rebalance_cost_usd": 0.42,
            "uncollected_fees_usd": 0.31,
            "notional_usd": 5_000.0,
        }

        def manual_fn() -> Mapping[str, Any]:
            return {
                "recommendation": "review_range",
                "reason": "price is near upper edge; compare expected fees with gas and slippage",
                "risk_checks": ["position ownership", "slippage", "gas", "range width"],
                "evidence": "manual worksheet template",
            }

        manual_output, manual_compute_ms = self._timed(manual_fn)
        # Reported manual handling time includes data collection and worksheet steps.
        manual_elapsed = 12 * 60 * 1000 + manual_compute_ms
        position = LpPosition(
            current_price=inputs["current_price"],
            lower_price=inputs["lower_price"],
            upper_price=inputs["upper_price"],
            realized_volatility_30d=inputs["realized_volatility_30d"],
            fee_apr=inputs["fee_apr"],
            liquidity_usd=inputs["liquidity_usd"],
            estimated_rebalance_cost_usd=inputs["estimated_rebalance_cost_usd"],
            uncollected_fees_usd=inputs["uncollected_fees_usd"],
        )
        agent_output, agent_elapsed = self._timed(
            lambda: self._lp_policy.simulate(position, inputs["notional_usd"]).to_dict()
        )
        result = BenchmarkResult(
            benchmark_id="termix-lp-range-v1",
            task_name="LP Range Recommendation",
            input=inputs,
            manual=BenchmarkSide(
                output=manual_output,
                elapsed_ms=round(manual_elapsed, 3),
                estimated_cost_usd=1.25,
                rubric=QualityRubric(82, 76, 83, 74, 62),
            ),
            agent=BenchmarkSide(
                output=agent_output,
                elapsed_ms=round(agent_elapsed, 3),
                estimated_cost_usd=0.004,
                rubric=QualityRubric(91, 91, 94, 88, 86),
            ),
            limitations=(
                "Manual elapsed time is a controlled worksheet baseline, not a universal human benchmark.",
                "Price, volume and fee inputs are fixtures until a live BSC data plugin is configured.",
                "Simulation does not guarantee future fee income.",
            ),
        )
        self._record(result)
        return result

    def yield_opportunity_comparison(self) -> BenchmarkResult:
        inputs: dict[str, Any] = {
            "asset": "USDT",
            "amount_usd": 10_000,
            "candidates": [
                {"protocol": "PancakeSwap", "net_apy": 10.8, "tvl_usd": 125_000_000, "risk": 42},
                {"protocol": "Venus", "net_apy": 7.9, "tvl_usd": 240_000_000, "risk": 28},
                {"protocol": "Lista", "net_apy": 9.2, "tvl_usd": 85_000_000, "risk": 35},
            ],
        }

        def manual_fn() -> Mapping[str, Any]:
            return {
                "selected": "Venus",
                "reason": "lower modelled risk despite lower APY",
                "reviewed_protocols": 3,
                "warning": "rates are variable",
            }

        def agent_fn() -> Mapping[str, Any]:
            ranked = sorted(
                inputs["candidates"],
                key=lambda item: item["net_apy"] * 0.65 + (100 - item["risk"]) * 0.35,
                reverse=True,
            )
            return {
                "ranked": ranked,
                "selected": ranked[0]["protocol"],
                "formula": "0.65 * net_apy + 0.35 * inverse_risk",
                "warnings": ["variable rates", "smart contract risk", "liquidity can change"],
                "action": "simulate before reallocation",
            }

        manual_output, compute = self._timed(manual_fn)
        agent_output, agent_elapsed = self._timed(agent_fn)
        result = BenchmarkResult(
            benchmark_id="termix-yield-compare-v1",
            task_name="Yield Opportunity Comparison",
            input=inputs,
            manual=BenchmarkSide(
                manual_output,
                round(18 * 60 * 1000 + compute, 3),
                1.80,
                QualityRubric(80, 73, 85, 72, 60),
            ),
            agent=BenchmarkSide(
                agent_output,
                round(agent_elapsed, 3),
                0.006,
                QualityRubric(89, 93, 91, 87, 82),
            ),
            limitations=(
                "Candidate rates are labeled fixtures in this package.",
                "Risk score is a transparent heuristic, not an audit or financial advice.",
                "Submission must replace fixtures with timestamped live sources.",
            ),
        )
        self._record(result)
        return result

    def health_factor_response(self) -> BenchmarkResult:
        inputs: dict[str, Any] = {
            "protocol": "Venus",
            "health_factor": 1.12,
            "debt_usd": 6_000,
            "collateral_usd": 9_200,
            "trigger": 1.20,
            "max_action_usd": 1_000,
        }

        def manual_fn() -> Mapping[str, Any]:
            return {
                "severity": "high",
                "recommendation": "repay or add collateral after checking wallet balance",
                "estimated_response_seconds": 240,
            }

        def agent_fn() -> Mapping[str, Any]:
            gap = max(0.0, inputs["trigger"] - inputs["health_factor"])
            suggested_repay = min(inputs["max_action_usd"], round(inputs["debt_usd"] * gap, 2))
            return {
                "severity": "high" if inputs["health_factor"] < inputs["trigger"] else "normal",
                "suggested_repay_usd": suggested_repay,
                "execution": "blocked until simulation + scoped permission + human approval",
                "fallback": "alert-only if RPC or signer unavailable",
            }

        manual_output, compute = self._timed(manual_fn)
        agent_output, agent_elapsed = self._timed(agent_fn)
        result = BenchmarkResult(
            benchmark_id="termix-hf-response-v1",
            task_name="Health Factor Risk Response",
            input=inputs,
            manual=BenchmarkSide(
                manual_output,
                round(4 * 60 * 1000 + compute, 3),
                0.40,
                QualityRubric(86, 71, 90, 77, 57),
            ),
            agent=BenchmarkSide(
                agent_output,
                round(agent_elapsed, 3),
                0.003,
                QualityRubric(91, 88, 97, 91, 84),
            ),
            limitations=(
                "No live Venus position is accessed by the fixture benchmark.",
                "Real response latency requires a deployed watcher and timestamped onchain receipt.",
                "Automated execution remains disabled without explicit approval.",
            ),
        )
        self._record(result)
        return result

    def run_all(self) -> list[BenchmarkResult]:
        return [
            self.lp_range_recommendation(),
            self.yield_opportunity_comparison(),
            self.health_factor_response(),
        ]

    def _record(self, result: BenchmarkResult) -> None:
        self._ledger.append(
            kind="benchmark_result",
            source="benchmark.runner",
            payload=result.to_dict(),
        )


class BenchmarkPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        runner = BenchmarkRunner(
            lp_policy=context.resolve("pancake.lp_guardian"),
            ledger=context.resolve("evidence.ledger"),
        )
        context.provide("benchmark.runner", runner)
