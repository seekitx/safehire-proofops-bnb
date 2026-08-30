from __future__ import annotations

import asyncio
import json
from pathlib import Path

from proofops.plugins.adversarial import Proposal
from proofops.services.bootstrap import build_application


async def main() -> None:
    app = await build_application()
    try:
        root = Path.cwd()
        benchmark_dir = root / "evidence" / "benchmark"
        benchmark_dir.mkdir(parents=True, exist_ok=True)
        runner = app.harness.resolve("benchmark.runner")
        results = runner.run_all()
        for result in results:
            (benchmark_dir / f"{result.benchmark_id}.json").write_text(
                json.dumps(result.to_dict(), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        council = app.harness.resolve("design.council")
        decision = council.review(Proposal.safehire_default())
        (root / "evidence" / "judging-notes").mkdir(parents=True, exist_ok=True)
        (root / "evidence" / "judging-notes" / "adversarial-decision.json").write_text(
            json.dumps(decision.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"Seeded {len(results)} benchmark records; debate accepted={decision.accepted}")
    finally:
        await app.close()


if __name__ == "__main__":
    asyncio.run(main())
