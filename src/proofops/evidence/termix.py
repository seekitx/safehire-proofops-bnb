from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

RUBRIC_FIELDS = (
    "correctness",
    "completeness",
    "risk_awareness",
    "actionability",
    "evidence_quality",
)
ALLOWED_CATEGORIES = {
    "rebalancing",
    "grid_trading",
    "yield_optimisation",
    "health_factor_monitoring",
}


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read valid JSON: {path}") from exc


def _resolve_file(root: Path, raw: str, *, live: bool) -> Path:
    if not raw:
        raise ValueError("evidence file path is required")
    path = (root / raw).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"evidence path escapes project root: {raw}") from exc
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"evidence file is missing or empty: {raw}")
    lowered = str(path).lower()
    if live and any(marker in lowered for marker in ("fixture", "synthetic", "/demo")):
        raise ValueError(f"live report cannot use fixture/demo path: {raw}")
    return path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _timestamp(raw: Any, field: str) -> datetime:
    if not isinstance(raw, str):
        raise TypeError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def _run_record(root: Path, raw: Any, *, label: str, live: bool) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TypeError(f"{label} must be an object")
    started = _timestamp(raw.get("started_at"), f"{label}.started_at")
    finished = _timestamp(raw.get("finished_at"), f"{label}.finished_at")
    duration = (finished - started).total_seconds()
    if duration <= 0:
        raise ValueError(f"{label} finish time must be after start time")
    cost = float(raw.get("cost_usd", -1))
    if cost < 0:
        raise ValueError(f"{label}.cost_usd must be non-negative")
    cost_currency = str(raw.get("cost_currency", "USD")).strip().upper()
    if not cost_currency or len(cost_currency) > 12:
        raise ValueError(f"{label}.cost_currency must be a short currency label")
    cost_amount = float(raw.get("cost_amount", cost))
    if cost_amount < 0:
        raise ValueError(f"{label}.cost_amount must be non-negative")
    output_path = _resolve_file(root, str(raw.get("output_path", "")), live=live)
    return {
        "output_path": str(output_path.relative_to(root.resolve())),
        "output_sha256": _sha256(output_path),
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": round(duration, 3),
        "cost_usd": cost,
        "cost_currency": cost_currency,
        "cost_amount": cost_amount,
        "tooling": str(raw.get("tooling", "unspecified")),
    }


def _scores(raw: Any, label: str) -> dict[str, float]:
    if not isinstance(raw, dict):
        raise TypeError(f"{label} scores must be an object")
    result: dict[str, float] = {}
    for field in RUBRIC_FIELDS:
        value = float(raw.get(field, -1))
        if not 0 <= value <= 5:
            raise ValueError(f"{label}.{field} must be in [0, 5]")
        result[field] = value
    result["total"] = round(sum(result.values()), 3)
    return result


def build_termix_report(manifest_path: Path, *, project_root: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise TypeError("manifest must be a JSON object")
    mode = manifest.get("evidence_mode")
    if mode not in {"live", "fixture"}:
        raise ValueError("evidence_mode must be live or fixture")
    live = mode == "live"
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("manifest tasks must be a non-empty list")
    if live and len(tasks) < 3:
        raise ValueError("live TermiX report requires at least three comparison tasks")

    built: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(tasks):
        if not isinstance(raw, dict):
            raise TypeError(f"tasks[{index}] must be an object")
        task_id = str(raw.get("task_id", "")).strip()
        if not task_id or task_id in ids:
            raise ValueError("each task_id must be present and unique")
        ids.add(task_id)
        category = str(raw.get("category", ""))
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"unsupported task category: {category}")
        prompt = _resolve_file(project_root, str(raw.get("prompt_path", "")), live=live)
        agent = _run_record(project_root, raw.get("agent"), label="agent", live=live)
        manual = _run_record(project_root, raw.get("manual"), label="manual", live=live)
        score_block = raw.get("scores")
        if not isinstance(score_block, dict):
            raise TypeError("scores must contain agent and manual objects")
        agent_scores = _scores(score_block.get("agent"), "scores.agent")
        manual_scores = _scores(score_block.get("manual"), "scores.manual")
        reviewer = str(raw.get("reviewer", "")).strip()
        if live and (
            not reviewer
            or reviewer.lower() in {"unassigned", "pending", "placeholder"}
            or "replace-with" in reviewer.lower()
        ):
            raise ValueError(f"tasks[{index}].reviewer must name the real reviewer")
        if live and (agent_scores["total"] == 0 or manual_scores["total"] == 0):
            raise ValueError(f"tasks[{index}] live scores cannot be all zero")
        built.append(
            {
                "task_id": task_id,
                "category": category,
                "prompt_path": str(prompt.relative_to(project_root.resolve())),
                "prompt_sha256": _sha256(prompt),
                "agent": agent,
                "manual": manual,
                "scores": {"agent": agent_scores, "manual": manual_scores},
                "advantage": {
                    "time_saved_seconds": round(
                        manual["duration_seconds"] - agent["duration_seconds"], 3
                    ),
                    "cost_delta_usd": round(manual["cost_usd"] - agent["cost_usd"], 4),
                    "quality_delta": round(agent_scores["total"] - manual_scores["total"], 3),
                },
                "reviewer": reviewer or "unassigned",
            }
        )

    categories = sorted({item["category"] for item in built})
    agent_seconds = sum(item["agent"]["duration_seconds"] for item in built)
    manual_seconds = sum(item["manual"]["duration_seconds"] for item in built)
    return {
        "schema_version": "1.0",
        "evidence_mode": mode,
        "generated_at": datetime.now().astimezone().isoformat(),
        "method": "same_prompt_agent_vs_manual_with_raw_outputs",
        "task_count": len(built),
        "categories": categories,
        "tasks": built,
        "aggregate": {
            "agent_duration_seconds": round(agent_seconds, 3),
            "manual_duration_seconds": round(manual_seconds, 3),
            "time_saved_seconds": round(manual_seconds - agent_seconds, 3),
            "agent_cost_usd": round(sum(item["agent"]["cost_usd"] for item in built), 4),
            "manual_cost_usd": round(sum(item["manual"]["cost_usd"] for item in built), 4),
            "agent_quality_total": round(
                sum(item["scores"]["agent"]["total"] for item in built), 3
            ),
            "manual_quality_total": round(
                sum(item["scores"]["manual"]["total"] for item in built), 3
            ),
        },
        "honesty_boundary": (
            "Live report: file hashes and timestamps are preserved; independent reviewer identity still needs external verification."
            if live
            else "Fixture report: useful only for testing the evidence pipeline, not for a hackathon claim."
        ),
    }
