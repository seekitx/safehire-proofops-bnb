from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from proofops.judging.scorecard import build_judge_scorecard
from proofops.services.bootstrap import build_application


async def run(output: Path | None) -> int:
    application = await build_application()
    try:
        scorecard = build_judge_scorecard(Path.cwd(), application.submission.run())
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
    args = parser.parse_args()
    return asyncio.run(run(args.output))


if __name__ == "__main__":
    raise SystemExit(main())
