from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PROJECT_ROOT / "evidence" / "marketplace" / "live-agent-catalog.json"
A2A_ENDPOINT = "https://agent.brainonbnb.com/a2a"
BSC_RPC_URL = "https://bsc-dataseed.bnbchain.org"


async def _rpc(client: httpx.AsyncClient, method: str, params: list[Any]) -> Any:
    response = await client.post(
        BSC_RPC_URL,
        json={"jsonrpc": "2.0", "id": method, "method": method, "params": params},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") or "result" not in payload:
        raise ValueError(f"BSC RPC rejected {method}")
    return payload["result"]


async def refresh() -> dict[str, Any]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    agents = catalog.get("agents")
    if not isinstance(agents, list) or len(agents) != 4:
        raise ValueError("expected exactly four saved Agent registrations")

    request = {
        "jsonrpc": "2.0",
        "id": "safehire-catalog-refresh",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": "safehire-catalog-refresh",
                "parts": [{"kind": "data", "data": {"skill": "list"}}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=15) as client:
        chain_id = await _rpc(client, "eth_chainId", [])
        if int(chain_id, 16) != 56:
            raise ValueError("RPC is not BSC mainnet")

        successful_receipts = 0
        for agent in agents:
            tx_hash = str(agent.get("created_tx_hash", ""))
            receipt = await _rpc(client, "eth_getTransactionReceipt", [tx_hash])
            if not isinstance(receipt, dict) or int(str(receipt.get("status", "0x0")), 16) != 1:
                raise ValueError(f"registration receipt is missing or failed: {tx_hash}")
            successful_receipts += 1

        response = await client.post(A2A_ENDPOINT, json=request)
        response.raise_for_status()
        payload = response.json()

    result = payload.get("result") if isinstance(payload, dict) else None
    services = result.get("services") if isinstance(result, dict) else None
    if not isinstance(services, list) or result.get("can_sign") is not True:
        raise ValueError("A2A endpoint no longer advertises signed hiring")
    live_skill_ids = {
        str(service.get("id")) for service in services if isinstance(service, dict)
    }
    expected_skill_ids = {str(agent.get("skill_id")) for agent in agents}
    if not expected_skill_ids.issubset(live_skill_ids):
        raise ValueError("one or more saved Agent skills are no longer advertised")

    catalog["observed_at"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    catalog["a2a_list_verified"] = True
    catalog["verification"] = {
        "chain_id": 56,
        "successful_registration_receipts": successful_receipts,
        "a2a_can_sign": True,
        "a2a_skill_ids": sorted(expected_skill_ids),
    }
    CATALOG_PATH.write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return catalog["verification"]


if __name__ == "__main__":
    print(json.dumps(asyncio.run(refresh()), indent=2, ensure_ascii=False))
