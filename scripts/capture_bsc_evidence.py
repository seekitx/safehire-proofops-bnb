from __future__ import annotations

import argparse
import asyncio
import json
import re
from pathlib import Path

from proofops.integrations import BscNetworkService
from proofops.settings import Settings

ROOT = Path(__file__).resolve().parents[1]
SAFE_LABEL = re.compile(r"^[a-z0-9][a-z0-9-]{1,48}$")


async def capture(chain_id: int, tx_hash: str, label: str) -> Path:
    if not SAFE_LABEL.fullmatch(label):
        raise ValueError("label must use 2-49 lowercase letters, digits or hyphens")
    settings = Settings()
    service = BscNetworkService(
        testnet_rpc_url=settings.bsc_testnet_rpc_url,
        mainnet_rpc_url=settings.bsc_mainnet_rpc_url,
    )
    verification = await service.verify_transaction(chain_id, tx_hash)
    if not verification["found"]:
        raise ValueError("transaction was not found on the configured BSC network")
    if not verification["successful"]:
        raise ValueError("transaction receipt exists but status is not successful")
    receipt = verification["receipt"]
    record = {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "source": "testnet_evidence" if chain_id == 97 else "live_onchain",
        "chain_id": chain_id,
        "tx_hash": tx_hash,
        "successful": True,
        "explorer_url": verification["explorer_url"],
        "observed_at": verification["observed_at"],
        "block_number": int(receipt["blockNumber"], 16),
        "from": receipt.get("from"),
        "to": receipt.get("to"),
        "gas_used": int(receipt["gasUsed"], 16),
        "receipt": receipt,
        "honesty_boundary": "Captured from configured BSC JSON-RPC; manually open Explorer URL before submission.",
    }
    output = ROOT / "evidence" / "tx" / f"{label}.json"
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify and save a real BSC transaction receipt without any private key."
    )
    parser.add_argument("tx_hash")
    parser.add_argument("--chain-id", type=int, choices=(56, 97), default=97)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    output = asyncio.run(capture(args.chain_id, args.tx_hash, args.label))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
