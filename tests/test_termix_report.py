from __future__ import annotations

import json
from pathlib import Path

import pytest

from proofops.evidence import build_termix_report


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _task(root: Path, task_id: str, category: str) -> dict[str, object]:
    base = root / "evidence" / "termix" / "raw" / task_id
    _write(base / "prompt.txt", f"prompt {task_id}")
    _write(base / "agent.json", json.dumps({"answer": task_id}))
    _write(base / "manual.md", f"manual {task_id}")
    scores = {
        field: 4
        for field in (
            "correctness",
            "completeness",
            "risk_awareness",
            "actionability",
            "evidence_quality",
        )
    }
    return {
        "task_id": task_id,
        "category": category,
        "prompt_path": str((base / "prompt.txt").relative_to(root)),
        "agent": {
            "output_path": str((base / "agent.json").relative_to(root)),
            "started_at": "2026-08-30T10:00:00+08:00",
            "finished_at": "2026-08-30T10:01:00+08:00",
            "cost_usd": 0.01,
        },
        "manual": {
            "output_path": str((base / "manual.md").relative_to(root)),
            "started_at": "2026-08-30T10:05:00+08:00",
            "finished_at": "2026-08-30T10:15:00+08:00",
            "cost_usd": 0,
        },
        "scores": {"agent": scores, "manual": {**scores, "actionability": 3}},
        "reviewer": "reviewer-1",
    }


def test_live_report_requires_raw_files_and_computes_advantage(tmp_path) -> None:
    tasks = [
        _task(tmp_path, "task-1", "rebalancing"),
        _task(tmp_path, "task-2", "grid_trading"),
        _task(tmp_path, "task-3", "health_factor_monitoring"),
    ]
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"evidence_mode": "live", "tasks": tasks}), encoding="utf-8")

    report = build_termix_report(manifest, project_root=tmp_path)

    assert report["task_count"] == 3
    assert report["aggregate"]["time_saved_seconds"] == 1620
    assert report["tasks"][0]["agent"]["output_sha256"]
    assert report["tasks"][0]["advantage"]["quality_delta"] == 1


def test_live_report_rejects_fixture_paths(tmp_path) -> None:
    task = _task(tmp_path, "fixture-task", "rebalancing")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"evidence_mode": "live", "tasks": [task, task, task]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="fixture/demo path|unique"):
        build_termix_report(manifest, project_root=tmp_path)
