from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Merge a completed blind review with its separately held mapping key."
    )
    parser.add_argument("packet", type=Path)
    parser.add_argument("secret_key", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    packet = _load(args.packet)
    secret_key = _load(args.secret_key)
    review = _load(args.review)
    packet_ids = {
        str(packet.get("packet_id", "")),
        str(secret_key.get("packet_id", "")),
        str(review.get("packet_id", "")),
    }
    if "" in packet_ids or len(packet_ids) != 1:
        raise ValueError("packet, key and review do not share one packet_id")
    mapping = secret_key.get("mapping")
    scores = review.get("scores")
    if not isinstance(mapping, dict) or set(mapping) != {"A", "B"}:
        raise ValueError("secret key mapping is invalid")
    if not isinstance(scores, dict) or set(scores) != {"A", "B"}:
        raise ValueError("blind review scores are invalid")
    origin_to_side = {str(origin): side for side, origin in mapping.items()}
    if set(origin_to_side) != {"agent", "manual"}:
        raise ValueError("secret key must map one Agent and one manual output")

    result = {
        "schema_version": "safehire-termix-unblinded-review-v2",
        "evidence_mode": "human_timed_and_blind_reviewed",
        "packet_id": packet["packet_id"],
        "task_id": packet.get("task_id"),
        "reviewer": review.get("reviewer"),
        "reviewed_at": review.get("reviewed_at"),
        "unblinded_at": datetime.now(UTC).isoformat(),
        "rubric": review.get("rubric"),
        "scores": {
            "agent": scores[origin_to_side["agent"]],
            "manual": scores[origin_to_side["manual"]],
        },
        "totals": {
            "agent": review.get("totals", {}).get(origin_to_side["agent"]),
            "manual": review.get("totals", {}).get(origin_to_side["manual"]),
        },
        "artifacts": {
            "packet": str(args.packet),
            "secret_key": str(args.secret_key),
            "review": str(args.review),
        },
        "honesty_boundary": (
            "The browser recorded the reviewer attestation and scores. SafeHire cannot prove "
            "the reviewer's independence without external identity evidence."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
