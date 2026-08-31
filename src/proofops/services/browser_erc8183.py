from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
from eth_abi.abi import decode, encode
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

BSC_TESTNET_RPC = "https://bsc-testnet-rpc.publicnode.com"
EXPECTED_BUYER = "0xe144264e2b71ec885cb10a10c6881b45fdf54f5f"
PRICE_RAW = 100_000_000_000_000_000
STATUS_NAMES = ("OPEN", "FUNDED", "SUBMITTED", "COMPLETED", "REJECTED", "EXPIRED")
VERDICT_NAMES = ("UNDECIDED", "APPROVE", "REJECT")


def _call_data(signature: str, types: list[str], values: list[Any]) -> str:
    return f"0x{(keccak(text=signature)[:4] + encode(types, values)).hex()}"


def _load_plan(project_root: Path, *, require_fresh: bool = True) -> dict[str, Any]:
    path = project_root / ".data" / "erc8183" / "browser-plan.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("verified ERC-8183 quote plan is missing; prepare a fresh quote") from exc
    if not isinstance(payload, dict) or payload.get("quote_verified") is not True:
        raise ValueError("ERC-8183 quote plan is not marked as verified")
    if payload.get("chain_id") != 97 or payload.get("price_raw") != str(PRICE_RAW):
        raise ValueError("ERC-8183 quote plan has an unexpected chain or price")
    description = json.loads(str(payload.get("description", "")))
    quote_expires_at = int(description.get("quote_expires_at", 0))
    if require_fresh and quote_expires_at <= int(time.time()) + 120:
        raise ValueError("signed 0.1 U quote is expired or too close to expiry; prepare a fresh quote")
    return payload


def initial_job_plan(project_root: Path, *, buyer: str) -> dict[str, Any]:
    if buyer.lower() != EXPECTED_BUYER:
        raise ValueError("connected wallet is not the approved SafeHire test buyer")
    plan = _load_plan(project_root)
    provider = to_checksum_address(str(plan["provider"]))
    commerce = to_checksum_address(str(plan["commerce_address"]))
    router = to_checksum_address(str(plan["router_address"]))
    description = str(plan["description"])
    expires_at = int(plan["expires_at"])
    return {
        "chain_id": 97,
        "network": "bsc-testnet",
        "buyer": to_checksum_address(buyer),
        "provider": provider,
        "price_raw": str(PRICE_RAW),
        "price_u": "0.1",
        "quote_expires_at": json.loads(description)["quote_expires_at"],
        "negotiation_hash": plan["negotiation_hash"],
        "job_created_topic": f"0x{keccak(text='JobCreated(uint256,address,address,address,uint256,address)').hex()}",
        "commerce_address": commerce,
        "transaction": {
            "step": "create_job",
            "label": "Create signed 0.1 U job",
            "to": commerce,
            "data": _call_data(
                "createJob(address,address,uint256,string,address)",
                ["address", "address", "uint256", "string", "address"],
                [provider, router, expires_at, description, router],
            ),
            "value": "0x0",
        },
    }


def followup_job_plan(project_root: Path, *, buyer: str, job_id: int) -> dict[str, Any]:
    if buyer.lower() != EXPECTED_BUYER or job_id <= 0:
        raise ValueError("buyer or job id is invalid")
    plan = _load_plan(project_root)
    commerce = to_checksum_address(str(plan["commerce_address"]))
    router = to_checksum_address(str(plan["router_address"]))
    policy = to_checksum_address(str(plan["policy_address"]))
    token = to_checksum_address(str(plan["token_address"]))
    return {
        "job_id": job_id,
        "price_raw": str(PRICE_RAW),
        "transactions": [
            {
                "step": "register_job",
                "label": "Bind official optimistic policy",
                "to": router,
                "data": _call_data(
                    "registerJob(uint256,address)",
                    ["uint256", "address"],
                    [job_id, policy],
                ),
                "value": "0x0",
            },
            {
                "step": "set_budget",
                "label": "Set exact 0.1 U budget",
                "to": commerce,
                "data": _call_data(
                    "setBudget(uint256,uint256,bytes)",
                    ["uint256", "uint256", "bytes"],
                    [job_id, PRICE_RAW, b""],
                ),
                "value": "0x0",
            },
            {
                "step": "approve_u",
                "label": "Approve exactly 0.1 U",
                "to": token,
                "data": _call_data(
                    "approve(address,uint256)",
                    ["address", "uint256"],
                    [commerce, PRICE_RAW],
                ),
                "value": "0x0",
            },
            {
                "step": "fund_job",
                "label": "Fund escrow with 0.1 U",
                "to": commerce,
                "data": _call_data(
                    "fund(uint256,uint256,bytes)",
                    ["uint256", "uint256", "bytes"],
                    [job_id, PRICE_RAW, b""],
                ),
                "value": "0x0",
            },
        ],
    }


async def settle_job_plan(project_root: Path, *, job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise ValueError("job id is invalid")
    status = await job_status(project_root, job_id=job_id)
    if status["completed"]:
        raise ValueError(f"job #{job_id} is already completed")
    if status["status"] != "SUBMITTED":
        raise ValueError(f"job #{job_id} is {status['status'].lower()}, not submitted")
    if not status["can_settle"]:
        seconds = int(status.get("seconds_until_settle", 0))
        if seconds > 0:
            raise ValueError(
                f"job #{job_id} is still inside the optimistic-policy dispute window; "
                f"retry after {seconds} seconds"
            )
        if status.get("disputed"):
            raise ValueError(f"job #{job_id} is disputed and is waiting for a policy verdict")
        raise ValueError(f"job #{job_id} has no final policy verdict yet")
    plan = _load_plan(project_root, require_fresh=False)
    router = to_checksum_address(str(plan["router_address"]))
    verdict = str(status.get("policy_verdict", "APPROVE"))
    label = (
        "Settle approved delivery and release 0.1 U"
        if verdict == "APPROVE"
        else "Finalize rejected delivery and return escrow"
    )
    return {
        "job_id": job_id,
        "policy_verdict": verdict,
        "transaction": {
            "step": "settle_job",
            "label": label,
            "to": router,
            "data": _call_data(
                "settle(uint256,bytes)",
                ["uint256", "bytes"],
                [job_id, b""],
            ),
            "value": "0x0",
        },
    }


def refund_job_plan(project_root: Path, *, job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise ValueError("job id is invalid")
    plan = _load_plan(project_root, require_fresh=False)
    commerce = to_checksum_address(str(plan["commerce_address"]))
    return {
        "job_id": job_id,
        "transaction": {
            "step": "refund_job",
            "label": "Refund expired 0.1 U escrow",
            "to": commerce,
            "data": _call_data("claimRefund(uint256)", ["uint256"], [job_id]),
            "value": "0x0",
        },
    }


async def job_status(project_root: Path, *, job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise ValueError("job id is invalid")
    plan = _load_plan(project_root, require_fresh=False)
    commerce = to_checksum_address(str(plan["commerce_address"]))
    data = _call_data("getJob(uint256)", ["uint256"], [job_id])
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": commerce, "data": data}, "latest"],
    }
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(BSC_TESTNET_RPC, json=request)
        response.raise_for_status()
        payload = response.json()
    if payload.get("error"):
        raise ValueError(f"BSC Testnet job read failed: {payload['error'].get('message', 'RPC error')}")
    raw = bytes.fromhex(str(payload["result"])[2:])
    fields = decode(
        ["(uint256,address,address,address,string,uint256,uint256,uint8,address,uint256,bytes32)"],
        raw,
    )[0]
    status_value = int(fields[7])
    status_name = STATUS_NAMES[status_value] if status_value < len(STATUS_NAMES) else "UNKNOWN"
    expired = int(fields[6]) <= int(time.time())
    result = {
        "job_id": int(fields[0]),
        "client": fields[1],
        "provider": fields[2],
        "evaluator": fields[3],
        "budget_raw": str(fields[5]),
        "budget_u": str(int(fields[5]) / 10**18),
        "expired_at": int(fields[6]),
        "status": status_name,
        "status_value": status_value,
        "submitted_at": int(fields[9]),
        "deliverable_hash": f"0x{fields[10].hex()}",
        "can_settle": False,
        "completed": status_value == 3,
        "expired": expired,
        "can_refund": status_value == 1 and expired,
    }
    if status_value != 2:
        return result

    policy = to_checksum_address(str(plan["policy_address"]))
    policy_calls = [
        ("check", _call_data("check(uint256,bytes)", ["uint256", "bytes"], [job_id, b""])),
        ("submitted_at", _call_data("submittedAt(uint256)", ["uint256"], [job_id])),
        ("dispute_window", _call_data("disputeWindow()", [], [])),
        ("disputed", _call_data("disputed(uint256)", ["uint256"], [job_id])),
    ]
    batch = [
        {
            "jsonrpc": "2.0",
            "id": index,
            "method": "eth_call",
            "params": [{"to": policy, "data": call_data}, "latest"],
        }
        for index, (_, call_data) in enumerate(policy_calls, start=1)
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(BSC_TESTNET_RPC, json=batch)
        response.raise_for_status()
        policy_payload = response.json()
    if not isinstance(policy_payload, list):
        raise ValueError("BSC Testnet policy read returned an unexpected response")
    responses = {int(item.get("id", 0)): item for item in policy_payload if isinstance(item, dict)}
    if len(responses) != len(policy_calls):
        raise ValueError("BSC Testnet policy read returned an incomplete batch")
    for index, (name, _) in enumerate(policy_calls, start=1):
        item = responses[index]
        if item.get("error"):
            message = item["error"].get("message", "RPC error")
            raise ValueError(f"BSC Testnet policy {name} read failed: {message}")

    verdict_value, reason = decode(
        ["uint8", "bytes32"], bytes.fromhex(str(responses[1]["result"])[2:])
    )
    policy_submitted_at = int(
        decode(["uint64"], bytes.fromhex(str(responses[2]["result"])[2:]))[0]
    )
    dispute_window = int(
        decode(["uint64"], bytes.fromhex(str(responses[3]["result"])[2:]))[0]
    )
    disputed = bool(decode(["bool"], bytes.fromhex(str(responses[4]["result"])[2:]))[0])
    settle_after = policy_submitted_at + dispute_window
    seconds_until_settle = max(0, settle_after - int(time.time()))
    verdict_name = (
        VERDICT_NAMES[verdict_value] if verdict_value < len(VERDICT_NAMES) else "UNKNOWN"
    )
    result.update(
        {
            "can_settle": verdict_value in {1, 2},
            "policy_verdict": verdict_name,
            "policy_verdict_value": verdict_value,
            "policy_reason": f"0x{reason.hex()}",
            "policy_submitted_at": policy_submitted_at,
            "dispute_window_seconds": dispute_window,
            "settle_after": settle_after,
            "seconds_until_settle": seconds_until_settle,
            "disputed": disputed,
        }
    )
    return result
