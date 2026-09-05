"""Read-only replay of an exact SafeHire ERC-8183 settlement.

No RPC write method, private key, approval, or transaction broadcast exists here.
RPC trust is explicit: this is not a light-client inclusion proof or a security audit.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

COMMERCE = "0xea4daa3100a767e86fded867729ae7446476eba6"
ROUTER = "0x51895229e12f9876011789b04f8698af06ccd6da"
TOKEN = "0xce24439f2d9c6a2289f741120fe202248b666666"
RPC = "https://bsc-dataseed.bnbchain.org"
IDENTITY_REGISTRY = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class VerifiedDelivery:
    chain_id: int
    job_id: int
    settlement_tx_hash: str
    provider: str
    buyer: str
    token_id: int
    skill_id: str
    provider_payment_raw: int
    output_commitment: str
    block_hash: str
    confirmations: int
    verified_at: str

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "verification_mode": "fresh_read_only_rpc_replay",
                "quality_verified": False, "business_independence_verified": False,
                "trust_boundary": "Trusted RPC observation; not a light-client proof or proof of useful output."}


class Reader(Protocol):
    async def settlement(self, tx_hash: str) -> dict[str, Any]: ...
    async def job(self, job_id: int, block_hash: str) -> dict[str, Any]: ...
    async def canonical_block_hash(self, block_number: int) -> str: ...
    async def identity(self, token_id: int, block_hash: str) -> dict[str, str]: ...
    def commitment(self, payload: bytes) -> str: ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


async def verify_delivery(claim: dict[str, Any], output: bytes, reader: Reader,
                          *, reviewed_agents: list[dict[str, Any]]) -> VerifiedDelivery:
    tx_hash, job_id = claim.get("settlement_tx_hash"), claim.get("job_id")
    _require(isinstance(tx_hash, str) and bool(HASH.fullmatch(tx_hash)), "Invalid settlement hash")
    _require(type(job_id) is int and 0 < job_id < 2**256, "Invalid job ID")
    _require(claim.get("chain_id") == 56 and type(claim.get("chain_id")) is int, "BSC mainnet only")
    _require(0 < len(output) <= 2 * 1024 * 1024, "Deliverable preimage must be 1 byte..2 MiB")
    _require(claim.get("commitment_scheme") == "keccak256_exact_utf8_bytes", "Explicit supported commitment scheme required")
    output.decode("utf-8")
    for key in ("buyer", "provider"):
        _require(isinstance(claim.get(key), str) and bool(ADDRESS.fullmatch(claim[key])), f"Invalid {key}")
    _require(claim["buyer"].lower() != claim["provider"].lower(), "Same-wallet self-hire excluded")
    _require(type(claim.get("token_id")) is int and claim["token_id"] > 0, "Invalid registry ID")
    _require(any(type(item.get("token_id")) is int and item.get("token_id") == claim.get("token_id")
                 and item.get("skill_id") == claim.get("skill_id") for item in reviewed_agents),
             "Identity and skill pair are outside reviewed catalog")
    snapshot = await reader.settlement(tx_hash)
    _require(snapshot.get("chain_id") == 56, "RPC chain ID mismatch")
    _require(snapshot.get("status") == 1, "Pending, failed, or missing transaction")
    _require(str(snapshot.get("tx_hash", "")).lower() == tx_hash.lower(), "Receipt transaction mismatch")
    _require(str(snapshot.get("to", "")).lower() == ROUTER, "Settlement must target reviewed router")
    _require(snapshot.get("function") == "settle(uint256,bytes)" and snapshot.get("job_id") == job_id,
             "Settlement calldata does not bind this job")
    _require(type(snapshot.get("confirmations")) is int and snapshot["confirmations"] >= 12,
             "At least 12 observed confirmations required")
    block_hash = str(snapshot.get("block_hash", ""))
    _require(bool(HASH.fullmatch(block_hash)), "Missing settlement block hash")
    identity = await reader.identity(claim["token_id"], block_hash)
    _require(str(identity.get("wallet", "")).lower() == claim["provider"].lower(),
             "Provider is not the registry agent wallet at the settlement block")
    _require(str(identity.get("owner", "")).lower() != claim["buyer"].lower(),
             "Buyer owns the agent; self-hire excluded")
    job = await reader.job(job_id, block_hash)
    _require(job.get("job_id") == job_id and job.get("status") == "COMPLETED", "Job is not completed at settlement block")
    _require(str(job.get("buyer", "")).lower() == claim["buyer"].lower(), "Buyer mismatch")
    _require(str(job.get("provider", "")).lower() == claim["provider"].lower(), "Provider mismatch")
    description = job.get("description")
    _require(isinstance(description, dict), "Missing bound task description")
    _require(description.get("schema_version") == "safehire-live-hire-v1", "Unreviewed job schema")
    _require(description.get("service") == claim.get("skill_id") and description.get("erc8004_token_id") == claim.get("token_id"),
             "Job description does not bind registry identity and skill")
    _require(str(description.get("provider", "")).lower() == claim["provider"].lower(), "Description provider mismatch")
    budget = job.get("budget_raw")
    _require(type(budget) is int and budget > 0 and str(budget) == str(description.get("price_raw")), "Budget mismatch")
    commitment = reader.commitment(output)
    _require(str(job.get("deliverable_hash", "")).lower() == commitment.lower(), "Deliverable bytes do not match onchain commitment")
    payment = sum(event["amount_raw"] for event in snapshot.get("transfers", [])
                  if isinstance(event, dict) and type(event.get("amount_raw")) is int and event["amount_raw"] > 0
                  and str(event.get("token", "")).lower() == TOKEN
                  and str(event.get("from", "")).lower() == COMMERCE
                  and str(event.get("to", "")).lower() == claim["provider"].lower())
    _require(0 < payment <= budget, "No matching escrow-to-provider payment within budget")
    canonical_hash = await reader.canonical_block_hash(snapshot["block_number"])
    _require(canonical_hash.lower() == block_hash.lower(), "Settlement block was reorganized")
    return VerifiedDelivery(56, job_id, tx_hash.lower(), claim["provider"].lower(), claim["buyer"].lower(),
                            claim["token_id"], claim["skill_id"], payment, commitment, block_hash,
                            snapshot["confirmations"], datetime.now(UTC).isoformat())


class BscReader:
    """Pinned existing deployment ABI. Unsupported nodes/ABIs fail closed."""

    def __init__(self) -> None:
        try:
            from eth_abi import decode, encode
            from eth_utils import keccak
        except ImportError as exc:
            raise RuntimeError("Install the project's declared dependencies: pip install -e '.[dev]'") from exc
        self.decode, self.encode, self.keccak = decode, encode, keccak

    async def rpc(self, method: str, params: list[Any]) -> Any:
        allowed = {"eth_chainId", "eth_blockNumber", "eth_getTransactionReceipt",
                   "eth_getTransactionByHash", "eth_call", "eth_getBlockByNumber"}
        if method not in allowed:
            raise ValueError("RPC method is not read-only allowlisted")
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.post(RPC, json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
            response.raise_for_status()
            if len(response.content) > 2 * 1024 * 1024:
                raise ValueError("RPC response exceeds 2 MiB")
            value = response.json()
        if not isinstance(value, dict) or value.get("error") or "result" not in value:
            raise ValueError("RPC error or unexpected response")
        return value["result"]

    def commitment(self, payload: bytes) -> str:
        return "0x" + self.keccak(payload).hex()

    async def settlement(self, tx_hash: str) -> dict[str, Any]:
        chain = int(await self.rpc("eth_chainId", []), 16)
        _require(chain == 56, "RPC chain ID mismatch")
        receipt = await self.rpc("eth_getTransactionReceipt", [tx_hash])
        tx = await self.rpc("eth_getTransactionByHash", [tx_hash])
        _require(isinstance(receipt, dict) and isinstance(tx, dict), "Pending or missing settlement")
        _require(str(receipt.get("transactionHash", "")).lower() == tx_hash.lower() and
                 str(tx.get("hash", "")).lower() == tx_hash.lower(), "Transaction hash mismatch")
        _require(tx.get("blockHash") == receipt.get("blockHash") and
                 tx.get("blockNumber") == receipt.get("blockNumber"), "Mixed transaction/receipt blocks")
        data = bytes.fromhex(str(tx.get("input", "0x"))[2:])
        selector = self.keccak(text="settle(uint256,bytes)")[:4]
        _require(data[:4] == selector, "Unsupported settlement selector")
        job_id, extra = self.decode(["uint256", "bytes"], data[4:])
        _require(self.encode(["uint256", "bytes"], [job_id, extra]) == data[4:], "Noncanonical settlement calldata")
        topic0 = "0x" + self.keccak(text="Transfer(address,address,uint256)").hex()
        transfers = []
        for log in receipt.get("logs", []):
            topics = log.get("topics", [])
            if len(topics) == 3 and str(topics[0]).lower() == topic0 and not log.get("removed"):
                if all(HASH.fullmatch(str(topic)) for topic in topics) and HASH.fullmatch(str(log.get("data"))):
                    transfers.append({"token": log["address"], "from": "0x" + topics[1][-40:],
                                      "to": "0x" + topics[2][-40:], "amount_raw": int(log["data"], 16)})
        block = int(receipt["blockNumber"], 16)
        head = int(await self.rpc("eth_blockNumber", []), 16)
        return {"chain_id": chain, "status": int(receipt["status"], 16), "tx_hash": tx_hash,
                "to": tx.get("to"), "job_id": job_id, "function": "settle(uint256,bytes)",
                "block_number": block, "block_hash": receipt["blockHash"],
                "confirmations": head - block + 1, "transfers": transfers}

    async def job(self, job_id: int, block_hash: str) -> dict[str, Any]:
        data = "0x" + (self.keccak(text="getJob(uint256)")[:4] + self.encode(["uint256"], [job_id])).hex()
        # Never downgrade to latest state: that would lose receipt/job block binding.
        raw = await self.rpc("eth_call", [{"to": COMMERCE, "data": data},
                                        {"blockHash": block_hash, "requireCanonical": True}])
        fields = self.decode(["(uint256,address,address,address,string,uint256,uint256,uint8,address,uint256,bytes32)"],
                             bytes.fromhex(raw[2:]))[0]
        return {"job_id": fields[0], "buyer": fields[1], "provider": fields[2],
                "description": json.loads(fields[4]), "budget_raw": fields[5],
                "status": "COMPLETED" if fields[7] == 3 else "NOT_COMPLETED",
                "deliverable_hash": "0x" + fields[10].hex()}

    async def identity(self, token_id: int, block_hash: str) -> dict[str, str]:
        result = {}
        for key, signature in (("wallet", "getAgentWallet(uint256)"), ("owner", "ownerOf(uint256)")):
            data = "0x" + (self.keccak(text=signature)[:4] + self.encode(["uint256"], [token_id])).hex()
            raw = await self.rpc("eth_call", [{"to": IDENTITY_REGISTRY, "data": data},
                                            {"blockHash": block_hash, "requireCanonical": True}])
            address = self.decode(["address"], bytes.fromhex(raw[2:]))[0]
            _require(address.lower() != "0x" + "0" * 40, "Unset registry wallet or owner")
            result[key] = address
        return result

    async def canonical_block_hash(self, block_number: int) -> str:
        block = await self.rpc("eth_getBlockByNumber", [hex(block_number), False])
        _require(isinstance(block, dict), "Missing canonical block")
        return str(block.get("hash", ""))


async def replay_claim(root: Path, claim_path: Path, output_path: Path) -> VerifiedDelivery:
    claim = json.loads(claim_path.read_text(encoding="utf-8"))
    catalog = json.loads((root / "evidence/marketplace/live-agent-catalog.json").read_text(encoding="utf-8"))
    if output_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Deliverable exceeds 2 MiB")
    return await verify_delivery(claim, output_path.read_bytes(), BscReader(), reviewed_agents=catalog["agents"])
