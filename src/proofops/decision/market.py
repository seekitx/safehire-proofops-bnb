from __future__ import annotations

import asyncio
import copy
import math
import re
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

CATEGORIES: dict[str, dict[str, Any]] = {
    "rebalancing": {
        "label": "LP Rebalancing", "required_capability": "lp_range_execution",
        "question": "Can it reset an LP range, not merely price a portfolio rebalance?",
        "evidence_needed": ["LP position and pool", "range before / after", "net cost", "execution receipt"],
    },
    "grid_trading": {
        "label": "Grid Trading", "required_capability": "grid_order_management",
        "question": "Can it manage orders, with fees, slippage and gas included?",
        "evidence_needed": ["pool and price snapshot", "round-trip costs", "order lifecycle", "cancel / stop evidence"],
    },
    "yield_optimisation": {
        "label": "Yield Optimisation", "required_capability": "liquidity_routing",
        "question": "Does a move improve net yield after migration costs and risk?",
        "evidence_needed": ["current position", "comparable APR / APY", "break-even horizon", "routing receipt"],
    },
    "health_factor_monitoring": {
        "label": "Health Factor", "required_capability": "lending_position_protection",
        "question": "Does monitoring lead to a bounded protective action?",
        "evidence_needed": ["protocol position", "oracle / block", "stress and repay target", "alert / protection receipt"],
    },
}
# Reviewed scope of the existing catalog. A name/skill does not establish execution.
REVIEWED: dict[tuple[int, str], tuple[str, str, bool]] = {
    (304494, "rebalance_plan"): ("rebalancing", "portfolio_rebalance_analysis", False),
    (302258, "grid_plan"): ("grid_trading", "grid_cost_analysis", True),
    (304493, "yield_plan"): ("yield_optimisation", "yield_comparison_analysis", True),
    (302257, "health_factor"): ("health_factor_monitoring", "lending_position_analysis", True),
}
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


def freshness(timestamp: Any, now: datetime, ttl_seconds: int = 60) -> dict[str, Any]:
    """Timezone-aware source age; future / missing / naive dates never pass."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    try:
        stamp = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("naive source timestamp")
        age = (now - stamp).total_seconds()
        if not math.isfinite(age) or age < -5:
            raise ValueError("source timestamp is in the future")
    except (ValueError, TypeError, OverflowError):
        return {"status": "unknown", "age_seconds": None, "source_observed_at": timestamp}
    return {
        "status": "fresh" if age <= ttl_seconds else "stale",
        "age_seconds": round(max(age, 0), 3), "source_observed_at": timestamp,
    }


def owner_key(value: Any) -> str | None:
    return str(value).lower() if isinstance(value, str) and ADDRESS.fullmatch(value) else None


def project_market(raw: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    source_age = freshness(raw.get("observed_at"), now)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    rejected = 0
    for item in raw.get("agents", []):
        if not isinstance(item, Mapping):
            rejected += 1
            continue
        token_id, skill = item.get("token_id"), item.get("skill_id")
        category = item.get("category")
        if type(token_id) is not int or token_id <= 0 or not isinstance(skill, str) or category not in CATEGORIES:
            rejected += 1
            continue
        identifier = f"56:{token_id}"
        if identifier in seen:
            rejected += 1
            continue
        seen.add(identifier)
        signals = item.get("market_signals")
        signals = signals if isinstance(signals, Mapping) else {}
        owner = owner_key(signals.get("owner_address")) if signals.get("available") is True else None
        reviewed = REVIEWED.get((token_id, skill))
        reviewed_ok = reviewed is not None and reviewed[0] == category
        capability = reviewed[1] if reviewed is not None and reviewed_ok else "unreviewed"
        domain_fit = bool(reviewed is not None and reviewed_ok and reviewed[2])
        registration = bool(TX_HASH.fullmatch(str(item.get("created_tx_hash", ""))))
        callable_now = (item.get("currently_callable") is True and
                        raw.get("endpoint_reachable") is True and source_age["status"] == "fresh" and
                        not raw.get("refresh_error"))
        reasons: list[str] = []
        if source_age["status"] != "fresh":
            reasons.append("fresh_A2A_probe_required")
        if not callable_now:
            reasons.append("no_current_callable_service")
        if not reviewed_ok:
            reasons.append("provider_adapter_not_reviewed")
        if owner is None:
            reasons.append("owner_unresolved")
        if not registration:
            reasons.append("registration_reference_missing")
        if not domain_fit:
            reasons.append("official_category_scope_gap")
        reasons.extend(["paid_outcome_not_replayed", "execution_not_demonstrated"])
        eligible_for_analysis = callable_now and reviewed_ok and registration
        rows.append({
            "id": identifier, "token_id": token_id, "skill_id": skill,
            "name": str(item.get("name") or skill), "category": category,
            "description": str(item.get("description") or ""),
            "operator_label": str(item.get("operator") or raw.get("operator") or "Unknown"),
            "owner_address_from_index": owner,
            "owner_identity_basis": "index_asserted_not_independence_proof" if owner else "unresolved",
            "registration_reference_present": registration,
            "registered_identity_is_performance_proof": False,
            "registration_tx": item.get("created_tx_hash"),
            "probe": {**source_age, "callable": callable_now},
            "index": {
                "available": signals.get("available") is True,
                "source_observed_at": signals.get("endpoint_last_checked_at"),
                "freshness": freshness(signals.get("endpoint_last_checked_at"), now, 300),
                "health": signals.get("index_a2a_health"),
                "quality_score_is_execution_success_rate": False,
            },
            "capability": {
                "reviewed_scope": capability, "category_analysis_fit": domain_fit,
                "official_required_scope": CATEGORIES[category]["required_capability"],
                "execution_proven": False, "basis": "reviewed_catalog_description_not_delivery",
            },
            "verified_paid_outcomes": None,
            "paid_outcome_status": "not_replayed_in_this_view",
            "quote_price": None, "quote_price_status": "requires_fresh_negotiation",
            "analysis_hire_available": eligible_for_analysis,
            "execution_hire_available": False,
            "hire_url": "/hire-live?" + urlencode({"skill_id": skill}) if eligible_for_analysis else None,
            "evidence_gaps": reasons,
            "signal_disagreement": item.get("signal_disagreement"),
            "registration_url": f"https://bscscan.com/tx/{item.get('created_tx_hash')}" if registration else None,
        })
    # Readiness ordering, not paid promotion, expected returns, or an official score.
    rows.sort(key=lambda row: (
        row["category"], not row["analysis_hire_available"],
        not row["capability"]["category_analysis_fit"],
        row["owner_address_from_index"] is None, row["id"],
    ))
    owners = {row["owner_address_from_index"] for row in rows if row["owner_address_from_index"]}
    labels = {row["operator_label"].strip().casefold() for row in rows}
    coverage = []
    for category, details in CATEGORIES.items():
        group = [row for row in rows if row["category"] == category]
        coverage.append({"category": category, **details, "listing_count": len(group),
                         "analysis_hire_count": sum(row["analysis_hire_available"] for row in group),
                         "proven_execution_count": 0,
                         "same_category_choice": len(group) >= 2})
    return {
        "schema_version": "safehire-decision/1", "generated_at": now.isoformat(),
        "source": raw.get("source"), "probe": source_age,
        "refresh_error": raw.get("refresh_error") or raw.get("liveness_error"),
        "registration_snapshot_observed_at": raw.get("registration_snapshot_observed_at"),
        "listings": rows, "categories": coverage,
        "supplier_concentration": {
            "listing_count": len(rows), "distinct_owner_addresses_from_index": len(owners),
            "unresolved_owner_listings": sum(row["owner_address_from_index"] is None for row in rows),
            "declared_operator_labels": len(labels),
            "independent_businesses_verified": None,
            "warning": "Four skills are not four suppliers; distinct wallets do not prove independent businesses.",
        },
        "rejected_or_duplicate_rows": rejected,
        "ranking_method": "Within category: fresh callable analysis, category fit, resolved owner, stable registry ID.",
        "not_claimed": ["official_judge_score", "winning_probability", "expected_profit", "paid_quality", "execution_authority"],
    }


def compare_market(projected: Mapping[str, Any], identifiers: list[str]) -> dict[str, Any]:
    if not 2 <= len(identifiers) <= 3 or len(set(identifiers)) != len(identifiers):
        raise ValueError("Select two or three distinct agents in the same category")
    by_id = {row["id"]: row for row in projected["listings"]}
    if any(identifier not in by_id for identifier in identifiers):
        raise ValueError("Unknown registry ID")
    selected = [by_id[identifier] for identifier in identifiers]
    if len({row["category"] for row in selected}) != 1:
        raise ValueError("Cross-category rankings are not comparable")
    return {"category": selected[0]["category"], "agents": selected,
            "winner": None, "reason": "Evidence comparison only; no independently replayed paired outcome yet."}


class SnapshotCache:
    """Single-flight cache; failed refresh never becomes a new live observation.

    One cache per ASGI worker. Multi-worker deployments should use a shared cache
    before enabling a large public index. No per-user keys or arbitrary URLs.
    """

    def __init__(self, loader: Callable[[], Awaitable[dict[str, Any]]], *,
                 ttl: float = 20, timeout: float = 25,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.loader, self.ttl, self.timeout, self.clock = loader, ttl, timeout, clock
        self.lock = asyncio.Lock()
        self.value: dict[str, Any] | None = None
        self.expires = float("-inf")

    async def get(self) -> dict[str, Any]:
        if self.value is not None and self.clock() < self.expires:
            return copy.deepcopy(self.value)
        async with self.lock:
            if self.value is not None and self.clock() < self.expires:
                return copy.deepcopy(self.value)
            try:
                current = await asyncio.wait_for(self.loader(), timeout=self.timeout)
                if not isinstance(current, dict) or not isinstance(current.get("agents"), list):
                    raise ValueError("invalid upstream market shape")
                self.value = copy.deepcopy(current)
            except (TimeoutError, ValueError, TypeError, OSError, httpx.HTTPError) as exc:
                previous = copy.deepcopy(self.value or {"agents": [], "observed_at": None})
                previous["refresh_error"] = type(exc).__name__
                previous["endpoint_reachable"] = False
                self.value = previous
            self.expires = self.clock() + self.ttl
            return copy.deepcopy(self.value)
