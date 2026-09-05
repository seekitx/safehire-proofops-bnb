from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from proofops.decision.paid import replay_claim


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only BSC settlement replay. Never signs or spends.")
    parser.add_argument("claim", type=Path)
    parser.add_argument("deliverable", type=Path)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    try:
        result = asyncio.run(replay_claim(args.root, args.claim, args.deliverable))
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        # Network/ABI failures are failed verification, never a passing fallback.
        parser.exit(2, f"Verification not established: {type(exc).__name__}: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
