"""Validate genuine paired measurements or build a blind packet, offline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from proofops.decision.benchmark import create_blind_packet, validate_experiment


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--public-dir", type=Path)
    parser.add_argument("--private-dir", type=Path)
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        if bool(args.public_dir) != bool(args.private_dir):
            raise ValueError("Supply both public and private directories, or neither")
        result = (create_blind_packet(args.manifest.parent, manifest, args.public_dir, args.private_dir)
                  if args.public_dir else validate_experiment(args.manifest.parent, manifest))
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"Benchmark rejected: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
