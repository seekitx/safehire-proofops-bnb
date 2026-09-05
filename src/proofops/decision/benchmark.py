"""Paired measurement and blinded review packets. No fabricated measurements.

File validation establishes artifact integrity, not reviewer independence. A
packet never makes the independent-review gate pass merely by existing.
"""
from __future__ import annotations

import hashlib
import json
import math
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LIMIT = 2 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def bounded_file(root: Path, relative: str) -> bytes:
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError("Artifact path must be relative")
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError("Artifact path escapes bundle, is missing, or exceeds 2 MiB")
    data = path.read_bytes()
    if len(data) > LIMIT:
        raise ValueError("Artifact exceeds 2 MiB")
    return data


def timestamp(value: Any) -> datetime:
    try:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid measurement timestamp") from exc
    if result.tzinfo is None:
        raise ValueError("Measurement timestamps must include a timezone")
    return result


def validate_experiment(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Validate paired tasks; unequal prompts and zero-duration baselines fail."""
    if manifest.get("schema_version") != "safehire-paired/1":
        raise ValueError("Expected safehire-paired/1 schema")
    tasks = manifest.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 100:
        raise ValueError("Provide between one and 100 paired tasks")
    seen = set()
    measurements = []
    for task in tasks:
        task_id = task.get("task_id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or not task_id.strip() or task_id in seen:
            raise ValueError("Task IDs must be nonempty and unique")
        seen.add(task_id)
        prompt = bounded_file(root, task["prompt_path"])
        prompt_hash = digest(prompt)
        if prompt_hash != task.get("prompt_sha256"):
            raise ValueError("Prompt hash mismatch")
        sides = {}
        for side in ("agent", "manual"):
            run = task.get(side)
            if not isinstance(run, dict) or run.get("prompt_sha256") != prompt_hash:
                raise ValueError("Both runs must bind the same prompt")
            output = bounded_file(root, run["output_path"])
            if digest(output) != run.get("output_sha256"):
                raise ValueError("Output hash mismatch")
            # Plaintext/JSON only; browsers must not execute HTML from a packet.
            try:
                output.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise ValueError("Outputs must be UTF-8 text") from exc
            start, end = timestamp(run.get("started_at")), timestamp(run.get("finished_at"))
            duration = (end - start).total_seconds()
            if duration <= 0 or duration > 7 * 86400:
                raise ValueError("Measured duration must be positive and at most seven days")
            amount = run.get("cost_usd")
            if type(amount) not in (int, float) or not math.isfinite(amount) or amount < 0:
                raise ValueError("cost_usd must be a finite nonnegative measured number")
            basis = str(run.get("cost_basis", "")).strip()
            if not basis:
                raise ValueError("Record the cost basis, including what was excluded")
            sides[side] = {"duration_seconds": duration, "cost_usd": amount,
                           "cost_basis": basis, "output_sha256": digest(output)}
        measurements.append({"task_id": task_id, "category": str(task.get("category", "unknown")),
                             "agent": sides["agent"], "manual": sides["manual"],
                             "time_saved_seconds": sides["manual"]["duration_seconds"] - sides["agent"]["duration_seconds"],
                             "cost_saved_usd": sides["manual"]["cost_usd"] - sides["agent"]["cost_usd"]})
    return {"schema_version": "safehire-paired-report/1", "artifact_integrity_valid": True,
            "task_count": len(measurements), "tasks": measurements,
            "quality_advantage": None, "independent_review_verified": False,
            "measurement_authenticity": "recorded_by_operator_not_independently_attested",
            "warning": "Duration and cost are measured records; no automatic quality score or independent-review claim."}


def create_blind_packet(root: Path, manifest: dict[str, Any], public_dir: Path, private_dir: Path) -> dict[str, Any]:
    report = validate_experiment(root, manifest)
    public_dir, private_dir = public_dir.resolve(), private_dir.resolve()
    if public_dir == private_dir or public_dir.is_relative_to(private_dir) or private_dir.is_relative_to(public_dir):
        raise ValueError("Keep the private reveal separate from the public packet")
    if public_dir.exists() or private_dir.exists():
        raise ValueError("Output directories must be new; never overwrite an existing evaluation")
    prepared = []
    reveal: dict[str, Any] = {"salt": secrets.token_hex(32), "mapping": {}}
    tasks = []
    for index, task in enumerate(manifest["tasks"], start=1):
        blind_id = f"case-{index:03d}"
        sides = ["agent", "manual"]
        if secrets.randbits(1):
            sides.reverse()
        reveal["mapping"][blind_id] = {"A": sides[0], "B": sides[1], "task_id": task["task_id"]}
        prepared.append((f"{blind_id}/prompt.txt", bounded_file(root, task["prompt_path"])))
        hashes = {}
        for label, side in zip(("A", "B"), sides, strict=True):
            data = bounded_file(root, task[side]["output_path"])
            prepared.append((f"{blind_id}/{label}.txt", data))
            hashes[label] = digest(data)
        tasks.append({"case_id": blind_id, "prompt_sha256": task["prompt_sha256"], "output_sha256": hashes})
    public = {"schema_version": "safehire-blind/1", "created_at": datetime.now(UTC).isoformat(),
              "reveal_commitment_sha256": digest(canonical(reveal)), "tasks": tasks,
              "rubric": {key: "Integer 0..5; cite a specific output passage" for key in
                         ("accuracy", "completeness", "source_quality", "safety", "actionability")},
              "warning": "Blind labels hide provenance metadata, but output content may reveal its author. Record any unblinding."}
    public_dir.mkdir(parents=True)
    private_dir.mkdir(parents=True, mode=0o700)
    for relative, data in prepared:
        path = public_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (public_dir / "packet.json").write_bytes(canonical(public))
    reveal_path = private_dir / "reveal.json"
    reveal_path.write_bytes(canonical(reveal))
    reveal_path.chmod(0o600)
    (private_dir / "measurements.json").write_bytes(canonical(report))
    return public
