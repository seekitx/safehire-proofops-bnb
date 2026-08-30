from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from proofops.domain.errors import AdapterUnavailableError

NETWORKS = {
    56: {
        "name": "BSC Mainnet",
        "explorer": "https://bscscan.com",
    },
    97: {
        "name": "BSC Testnet",
        "explorer": "https://testnet.bscscan.com",
    },
}


def explorer_url(chain_id: int, kind: str, value: str) -> str:
    network = NETWORKS.get(chain_id)
    if network is None:
        raise ValueError(f"unsupported BSC chain id: {chain_id}")
    if kind not in {"tx", "address"}:
        raise ValueError("explorer kind must be tx or address")
    return f"{network['explorer']}/{kind}/{value}"


class BscRpcClient:
    def __init__(self, rpc_url: str, *, timeout_seconds: float = 8.0) -> None:
        self._rpc_url = rpc_url
        self._timeout = timeout_seconds

    async def call(self, method: str, params: list[Any]) -> Any:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    self._rpc_url,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            safe_message = re.sub(r"\S+://\S+", "<redacted-rpc>", str(exc))
            raise AdapterUnavailableError(f"BSC RPC unavailable: {safe_message}") from exc
        if payload.get("error"):
            message = payload["error"].get("message", "unknown")
            raise AdapterUnavailableError(f"BSC RPC error: {message}")
        return payload.get("result")

    async def chain_id(self) -> int:
        result = await self.call("eth_chainId", [])
        return int(str(result), 16)

    async def block_number(self) -> int:
        result = await self.call("eth_blockNumber", [])
        return int(str(result), 16)

    async def transaction_receipt(self, tx_hash: str) -> dict[str, Any] | None:
        result = await self.call("eth_getTransactionReceipt", [tx_hash])
        return result if isinstance(result, dict) else None

    async def contract_code(self, address: str) -> str:
        result = await self.call("eth_getCode", [address, "latest"])
        return str(result or "0x")


class BscNetworkService:
    def __init__(self, *, testnet_rpc_url: str, mainnet_rpc_url: str) -> None:
        self._clients = {
            97: BscRpcClient(testnet_rpc_url),
            56: BscRpcClient(mainnet_rpc_url),
        }

    async def status(self, chain_id: int = 97) -> dict[str, Any]:
        if chain_id not in self._clients:
            raise ValueError("chain_id must be 56 or 97")
        client = self._clients[chain_id]
        actual_chain_id = await client.chain_id()
        if actual_chain_id != chain_id:
            raise AdapterUnavailableError(
                f"configured RPC returned chain {actual_chain_id}, expected {chain_id}"
            )
        return {
            "chain_id": chain_id,
            "name": NETWORKS[chain_id]["name"],
            "block_number": await client.block_number(),
            "explorer": NETWORKS[chain_id]["explorer"],
            "observed_at": datetime.now(UTC).isoformat(),
            "source": "live_bsc_rpc",
        }

    async def verify_transaction(self, chain_id: int, tx_hash: str) -> dict[str, Any]:
        if not re.fullmatch(r"0x[a-fA-F0-9]{64}", tx_hash):
            raise ValueError("tx_hash must be a 32-byte hex value")
        receipt = await self._clients[chain_id].transaction_receipt(tx_hash)
        return {
            "found": receipt is not None,
            "successful": bool(receipt and int(receipt.get("status", "0x0"), 16) == 1),
            "receipt": receipt,
            "explorer_url": explorer_url(chain_id, "tx", tx_hash),
            "observed_at": datetime.now(UTC).isoformat(),
        }
