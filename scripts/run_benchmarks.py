from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from proofops.services.bootstrap import build_application


async def main() -> None:
    app = await build_application()
    try:
        out = Path("evidence/benchmark")
        out.mkdir(parents=True, exist_ok=True)
        runner = app.harness.resolve("benchmark.runner")
        for result in runner.run_all():
            payload = result.to_dict()
            payload["generated_at"] = datetime.now(UTC).isoformat()
            payload["source_label"] = "benchmark_generated"
            path = out / f"{result.benchmark_id}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            print(path)
    finally:
        await app.close()


if __name__ == "__main__":
    asyncio.run(main())
