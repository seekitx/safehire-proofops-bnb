from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from proofops.judging.scorecard import build_judge_scorecard
from proofops.decision.paid import VerifiedDelivery, replay_claim
from proofops.services.bootstrap import build_application


async def run(output: Path | None, paid_claim: Path | None = None, deliverable: Path | None = None) -> int:
    application = await build_application()
    try:
        verified: tuple[VerifiedDelivery, ...] = ()
        if paid_claim is not None and deliverable is not None:
            verified = (await replay_claim(Path.cwd(), paid_claim, deliverable),)
        scorecard = build_judge_scorecard(Path.cwd(), application.submission.run(), verified_deliveries=verified)
    finally:
        await application.close()
    rendered = json.dumps(scorecard, ensure_ascii=False, indent=2) + "\n"
    if output is None:
        print(rendered, end="")
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(output)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a judge-facing self-audit without inventing an official score."
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--paid-claim", type=Path, help="Explicit read-only RPC replay; requires --deliverable")
    parser.add_argument("--deliverable", type=Path)
    args = parser.parse_args()
    if bool(args.paid_claim) != bool(args.deliverable):
        parser.error("--paid-claim and --deliverable must be supplied together")
    return asyncio.run(run(args.output, args.paid_claim, args.deliverable))


if __name__ == "__main__":
    raise SystemExit(main())
