from __future__ import annotations

import asyncio
import json

from proofops.services.bootstrap import build_application


async def main() -> None:
    app = await build_application()
    try:
        result = app.harness.resolve("evidence.ledger").verify()
        print(json.dumps(result, indent=2))
        print("Anchor head_hash in EvidenceAnchor.sol after a real BSC deployment.")
    finally:
        await app.close()


if __name__ == "__main__":
    asyncio.run(main())
