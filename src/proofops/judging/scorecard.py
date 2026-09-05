from __future__ import annotations

import json
import re
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proofops.decision.market import freshness
from proofops.decision.paid import VerifiedDelivery

REQUIRED_CATEGORIES = (
    "rebalancing",
    "grid_trading",
    "yield_optimisation",
    "health_factor_monitoring",
)
OFFICIAL_RULES_URL = "https://www.bnbchain.org/en/hackathons/smart-money-era?tab=tracks"
TX_HASH = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _rows(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _submission_check_passed(result: Mapping[str, Any], check_id: str) -> bool:
    for check in _rows(result.get("checks")):
        if check.get("check_id") == check_id:
            return check.get("passed") is True
    return False


def _completed_testnet_hire(record: Mapping[str, Any]) -> bool:
    expected = {
        "create_job",
        "register_job",
        "set_budget",
        "approve_u",
        "fund_job",
        "submit_delivery",
        "settle_job",
    }
    steps = {
        str(item.get("step"))
        for item in _rows(record.get("transactions"))
        if item.get("receipt_status") == 1
        and TX_HASH.fullmatch(str(item.get("tx_hash", "")))
    }
    verification = _mapping(record.get("verification"))
    return (
        record.get("chain_id") == 97
        and expected.issubset(steps)
        and verification.get("completed") is True
        and verification.get("provider_payment_transfer_observed") is True
    )


def _count_evidence_candidates(directory: Path) -> int:
    """Local JSON can claim anything; file presence is not verification."""
    return sum(1 for path in directory.glob("*.json") if _read_json(path)) if directory.is_dir() else 0


def _fresh_deliveries(records: tuple[VerifiedDelivery, ...], now: datetime) -> int:
    # Only in-memory results from the read-only replay path are accepted. Never
    # deserialize a stored {paid: true, verification_mode: ...} into this type.
    return len({(row.chain_id, row.job_id) for row in records
                if isinstance(row, VerifiedDelivery) and row.chain_id == 56
                and row.provider_payment_raw > 0
                and freshness(row.verified_at, now, 300)["status"] == "fresh"})


def _category_parity(
    project_root: Path, catalog: Mapping[str, Any]
) -> list[dict[str, Any]]:
    agents = _rows(catalog.get("agents"))
    by_category = {str(item.get("category")): item for item in agents}
    live_hire_route = (
        (project_root / "apps" / "web" / "live-hire.html").is_file()
        and (project_root / "src" / "proofops" / "services" / "live_erc8183.py").is_file()
    )
    rows: list[dict[str, Any]] = []
    for category in REQUIRED_CATEGORIES:
        agent = by_category.get(category, {})
        required_inputs = _mapping(agent.get("required_inputs"))
        token_id = agent.get("token_id")
        dimensions = {
            "category_specific_input": bool(required_inputs),
            "erc8004_identity": isinstance(token_id, int) and token_id > 0,
            "registration_transaction": bool(
                TX_HASH.fullmatch(str(agent.get("created_tx_hash", "")))
            ),
            "callable_skill": bool(str(agent.get("skill_id", "")).strip()),
            "quote_route": (
                project_root / "src" / "proofops" / "services" / "live_agent_market.py"
            ).is_file(),
            "hire_route": live_hire_route,
        }
        passed = sum(bool(value) for value in dimensions.values())
        rows.append(
            {
                "category": category,
                "skill_id": agent.get("skill_id"),
                "erc8004_token_id": token_id,
                "status": "ready" if passed == len(dimensions) else "blocked",
                "depth_coverage": f"{passed}/{len(dimensions)}",
                "coverage_kind": "route_structure_only_not_execution_depth",
                "actual_execution_depth_verified": False,
                "dimensions": dimensions,
            }
        )
    return rows


def build_judge_scorecard(
    project_root: Path,
    submission_result: Mapping[str, Any] | None = None,
    *,
    generated_at: datetime | None = None,
    verified_deliveries: tuple[VerifiedDelivery, ...] = (),
) -> dict[str, Any]:
    """Build a deterministic self-audit aligned to the published judge rubric.

    This deliberately avoids a weighted "official score": the event page names
    criteria but does not publish a numeric main-track weighting.
    """

    submission = submission_result or {}
    catalog = _read_json(
        project_root / "evidence" / "marketplace" / "live-agent-catalog.json"
    )
    job = _read_json(
        project_root / "evidence" / "sponsor-integration" / "erc8183-job-808.json"
    )
    termix = _read_json(
        project_root / "evidence" / "termix" / "agent-advantage-report.json"
    )
    pancake = _read_json(
        project_root / "evidence" / "pancakeswap" / "live-benefit-report.json"
    )

    parity = _category_parity(project_root, catalog)
    categories_ready = all(row["status"] == "ready" for row in parity)
    depth_values = {str(row["depth_coverage"]) for row in parity}
    equal_depth = categories_ready and len(depth_values) == 1

    now = generated_at or datetime.now(UTC)
    external_paid = _fresh_deliveries(verified_deliveries, now)
    paid_candidates = _count_evidence_candidates(
        project_root / "evidence" / "marketplace" / "paid-deliveries"
    )
    review_candidates = _count_evidence_candidates(
        project_root / "evidence" / "termix" / "v2" / "reviews"
    )
    # Authentication/conflict review is an explicit human signoff, not a boolean
    # supplied by a contestant's JSON file. Blind-packet tooling does not certify it.
    blind_reviews = 0
    operators = {
        str(item.get("operator") or catalog.get("operator") or "").strip()
        for item in _rows(catalog.get("agents"))
    }
    operator_count = len({item for item in operators if item})
    completed_testnet_hire = _completed_testnet_hire(job)
    live_hire_route = (
        project_root / "apps" / "web" / "live-hire.html"
    ).is_file() and (
        project_root / "src" / "proofops" / "services" / "live_erc8183.py"
    ).is_file()
    gate_ready = submission.get("ready") is True

    functionality_checks = {
        "submission_gate_ready": gate_ready,
        "live_bsc_catalog": _submission_check_passed(
            submission, "live_bsc_market_catalog"
        ),
        "four_category_parity": equal_depth,
        "live_hire_route_present": live_hire_route,
        "completed_erc8183_testnet_hire": completed_testnet_hire,
        "external_paid_delivery_captured": external_paid > 0,
    }
    functionality_status = (
        "ready"
        if all(functionality_checks.values())
        else "conditional"
        if all(
            functionality_checks[key]
            for key in (
                "submission_gate_ready",
                "live_bsc_catalog",
                "four_category_parity",
                "live_hire_route_present",
                "completed_erc8183_testnet_hire",
            )
        )
        else "blocked"
    )

    data_checks = {
        "live_snapshot": catalog.get("evidence_mode") == "live",
        "freshness_timestamp": freshness(catalog.get("observed_at"), now, 86400)["status"] == "fresh",
        "identity_and_registration_per_agent": all(
            bool(row["dimensions"]["erc8004_identity"])
            and bool(row["dimensions"]["registration_transaction"])
            for row in parity
        ),
        "category_specific_inputs": all(
            bool(row["dimensions"]["category_specific_input"]) for row in parity
        ),
        "raw_termix_outputs_hashed": _submission_check_passed(
            submission, "termix_live_advantage_report"
        ),
        "independent_blind_reviews": blind_reviews >= 3,
        "multiple_independent_operators": False,
        "paid_external_track_record": external_paid > 0,
    }
    core_data_keys = (
        "live_snapshot",
        "freshness_timestamp",
        "identity_and_registration_per_agent",
        "category_specific_inputs",
        "raw_termix_outputs_hashed",
    )
    data_status = (
        "ready"
        if all(data_checks.values())
        else "conditional"
        if all(data_checks[key] for key in core_data_keys)
        else "blocked"
    )

    diversity_checks = {
        "all_four_official_categories": categories_ready,
        "equal_depth_envelope": equal_depth,
        "second_independent_operator": False,
    }
    diversity_status = (
        "ready"
        if all(diversity_checks.values())
        else "conditional"
        if categories_ready and equal_depth
        else "blocked"
    )

    termix_tasks = _rows(termix.get("tasks"))
    termix_structure = (
        termix.get("evidence_mode") == "live"
        and len(termix_tasks) >= 3
        and _submission_check_passed(submission, "termix_live_advantage_report")
    )
    pancake_structure = (
        pancake.get("evidence_mode") == "live"
        and bool(str(pancake.get("measurable_benefit", "")).strip())
        and _submission_check_passed(submission, "pancakeswap_live_benefit")
    )
    altana_record = _read_json(
        project_root / "evidence" / "sponsor-integration" / "altana-session.json"
    )
    altana_ready = bool(
        altana_record.get("evidence_mode") == "live"
        and altana_record.get("session_transaction_verified") is True
        and altana_record.get("revocation_verified") is True
    )

    manual_gates = [
        {
            "id": "external_paid_delivery",
            "status": "complete" if external_paid > 0 else "manual_required",
            "action": "Complete one bounded 0.10 U external ERC-8183 hire from a live card.",
            "completion_evidence": (
                "Mainnet create/fund/deliver/settle receipts and the provider output."
            ),
            "why_it_matters": "Turns an implemented path into an auditable marketplace track record.",
        },
        {
            "id": "independent_blind_review",
            "status": "complete" if blind_reviews >= 3 else "manual_required",
            "action": "Collect at least three human no-Agent runs and independent blind reviews.",
            "completion_evidence": "Timestamped runs, blind packets, reviewer records and secret mapping.",
            "why_it_matters": "Makes the TermiX quality advantage credible instead of self-scored.",
        },
        {
            "id": "second_operator",
            "status": "manual_required",
            "action": "Onboard and verify a second independent ERC-8004 provider.",
            "completion_evidence": "Registration, callable endpoint, category fit and reviewed listing dossier.",
            "why_it_matters": "Proves marketplace choice rather than a four-skill catalog from one seller.",
        },
        {
            "id": "judge_delivery_reliability",
            "status": "manual_required",
            "action": "Use non-sleeping hosting during judging and record one 2–3 minute wow-path demo.",
            "completion_evidence": "Warm public URL, health check and public video.",
            "why_it_matters": "Prevents a cold start or scattered navigation from hiding the working product.",
        },
    ]

    return {
        "schema_version": "1.1",
        "evidence_integrity": {
            "paid_candidate_files": paid_candidates,
            "blind_review_candidate_files": review_candidates,
            "freshly_replayed_paid_deliveries": external_paid,
            "declared_operator_labels": operator_count,
            "independent_operators_verified": None,
            "catalog_freshness": freshness(catalog.get("observed_at"), now, 86400),
            "warning": "Candidate files, display labels and blind-packet presence are not independent proof.",
        },
        "generated_at": (generated_at or datetime.now(UTC)).isoformat(),
        "project": "SafeHire / ProofOps",
        "positioning": (
            "A proof-carrying BNB Chain Agent marketplace: compare evidence, cap authority, "
            "hire through ERC-8183 and settle against a reviewable delivery."
        ),
        "official_rubric": {
            "source_url": OFFICIAL_RULES_URL,
            "main_track_criteria": [
                "Functionality",
                "Data Quality",
                "Agent Diversity",
            ],
            "numeric_weights_published": False,
            "warning": "This is a deterministic project self-audit, not an official BNB Chain score.",
        },
        "readiness": {
            "submission_gate": "ready" if gate_ready else "blocked",
            "winner_readiness": (
                "ready"
                if all(item["status"] == "complete" for item in manual_gates)
                else "conditional"
            ),
            "headline": (
                "Working MVP with strong protocol evidence; winning claims remain conditional "
                "until real external usage and independent review are captured."
            ),
        },
        "main_track": {
            "functionality": {
                "status": functionality_status,
                "checks": functionality_checks,
                "judge_message": (
                    "The no-dead-end hire route exists and a full testnet settlement is proven; "
                    "the first paid external mainnet delivery is still missing."
                ),
            },
            "data_quality": {
                "status": data_status,
                "checks": data_checks,
                "judge_message": (
                    "Identity, registration, source and freshness are inspectable; paid outcome "
                    "history, independent review and supplier breadth remain thin."
                ),
            },
            "agent_diversity": {
                "status": diversity_status,
                "checks": diversity_checks,
                "judge_message": (
                    "All four official categories use the same six-dimension depth envelope; "
                    "all current live listings still share one operator."
                ),
            },
        },
        "category_parity": parity,
        "partner_tracks": {
            "termix": {
                "status": (
                    "ready"
                    if termix_structure and blind_reviews >= 3
                    else "conditional"
                    if termix_structure
                    else "blocked"
                ),
                "task_count": len(termix_tasks),
                "independent_blind_reviews": blind_reviews,
                "boundary": "Existing automated scores are a reproducible baseline, not independent research.",
            },
            "pancakeswap": {
                "status": "conditional" if pancake_structure else "blocked",
                "live_benefit_report": pancake_structure,
                "boundary": "The report proves quote/decision improvement, not realised trading profit.",
            },
            "altana": {
                "status": "ready" if altana_ready else "not_claimed",
                "boundary": (
                    "Do not claim this track without a real session-key transaction, scoped limits "
                    "and an in-product revocation receipt."
                ),
            },
        },
        "manual_gates": manual_gates,
        "judge_route": [
            {"step": 1, "path": "/", "proof": "Four live ERC-8004 categories and decision signals"},
            {"step": 2, "path": "/hire-live", "proof": "Quote-to-ERC-8183 wallet-confirmed hire"},
            {"step": 3, "path": "/proof", "proof": "Identity, job, contracts and measurable benefit"},
            {"step": 4, "path": "/benchmark", "proof": "Raw Agent/no-Agent evidence and blind review lab"},
        ],
        "honesty_boundary": (
            "No code change can manufacture a paid external delivery, an independent human review, "
            "a second provider or a stable paid host. Those remain explicit manual gates."
        ),
    }
