from __future__ import annotations

import copy
import json

import pytest

from proofops.decision.benchmark import bounded_file, canonical, create_blind_packet, digest, validate_experiment


@pytest.fixture
def experiment(tmp_path):
    files = {"prompt.txt": b"SYNTHETIC TEST TASK", "agent.txt": b"artificial agent output", "manual.txt": b"artificial manual output"}
    for name, value in files.items():
        (tmp_path / name).write_bytes(value)
    prompt = digest(files["prompt.txt"])
    sides = {side: {"prompt_sha256": prompt, "output_path": f"{side}.txt", "output_sha256": digest(files[f"{side}.txt"]),
             "started_at": "2026-09-05T00:00:00Z", "finished_at": "2026-09-05T00:00:30Z" if side == "agent" else "2026-09-05T00:05:00Z",
             "cost_usd": 0, "cost_basis": "Synthetic unit fixture; no actual bill"} for side in ("agent", "manual")}
    manifest = {"schema_version": "safehire-paired/1", "tasks": [{"task_id": "test-task", "category": "grid_trading",
                "prompt_path": "prompt.txt", "prompt_sha256": prompt, **sides}]}
    return tmp_path, manifest


def test_paired_result_is_arithmetic_not_automatic_quality(experiment):
    root, manifest = experiment
    report = validate_experiment(root, manifest)
    assert report["tasks"][0]["time_saved_seconds"] == 270
    assert report["quality_advantage"] is None and not report["independent_review_verified"]


@pytest.mark.parametrize("field,value", [("prompt_sha256", "bad"), ("output_sha256", "bad"),
    ("finished_at", "2026-09-05T00:00:00Z"), ("started_at", "2026-09-05T00:00:00"),
    ("cost_usd", float("nan")), ("cost_usd", True), ("cost_usd", -1), ("cost_basis", "")])
def test_invalid_baselines_rejected(experiment, field, value):
    root, manifest = experiment
    manifest["tasks"][0]["manual"][field] = value
    with pytest.raises(ValueError):
        validate_experiment(root, manifest)


def test_duplicate_task_does_not_count_as_multiple_trials(experiment):
    root, manifest = experiment
    manifest["tasks"].append(copy.deepcopy(manifest["tasks"][0]))
    with pytest.raises(ValueError, match="unique"):
        validate_experiment(root, manifest)


def test_changed_output_rejected(experiment):
    root, manifest = experiment
    (root / "agent.txt").write_text("changed")
    with pytest.raises(ValueError, match="hash"):
        validate_experiment(root, manifest)


def test_path_escape_and_symlink_escape_rejected(experiment):
    root, _ = experiment
    outside = root.parent / "secret.txt"
    outside.write_text("not an artifact")
    with pytest.raises(ValueError):
        bounded_file(root, "../secret.txt")
    (root / "alias.txt").symlink_to(outside)
    with pytest.raises(ValueError):
        bounded_file(root, "alias.txt")


def test_blind_packet_keeps_reveal_private_and_committed(experiment):
    root, manifest = experiment
    public, private = root / "public", root / "private"
    packet = create_blind_packet(root, manifest, public, private)
    reveal = json.loads((private / "reveal.json").read_text())
    assert digest(canonical(reveal)) == packet["reveal_commitment_sha256"]
    assert not (public / "reveal.json").exists()
    assert set(reveal["mapping"]["case-001"][label] for label in ("A", "B")) == {"agent", "manual"}
    assert (public / "case-001/A.txt").exists() and (public / "case-001/B.txt").exists()
    assert "task_id" not in json.dumps(packet)
    assert (private / "reveal.json").stat().st_mode & 0o077 == 0


def test_private_reveal_cannot_be_inside_public_packet(experiment):
    root, manifest = experiment
    with pytest.raises(ValueError, match="separate"):
        create_blind_packet(root, manifest, root / "public", root / "public/private")


def test_existing_packet_is_never_overwritten(experiment):
    root, manifest = experiment
    (root / "public").mkdir()
    with pytest.raises(ValueError, match="never overwrite"):
        create_blind_packet(root, manifest, root / "public", root / "private")
