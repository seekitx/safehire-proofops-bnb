from __future__ import annotations

import argparse
import asyncio
import json
import sys

from proofops.services.bootstrap import build_application


async def run(allow_incomplete: bool) -> int:
    app = await build_application()
    try:
        result = app.submission.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["ready"] or allow_incomplete:
            return 0
        print("\nSUBMISSION BLOCKED: replace fixtures with real BSC evidence.", file=sys.stderr)
        return 2
    finally:
        await app.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    return asyncio.run(run(args.allow_incomplete))


if __name__ == "__main__":
    raise SystemExit(main())
