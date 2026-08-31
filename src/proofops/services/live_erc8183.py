from __future__ import annotations

import json
import re
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from eth_abi.abi import decode, encode
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

from proofops.services.live_agent_market import A2A_ENDPOINT, request_live_agent_quote

BSC_MAINNET_RPC = "https://bsc-dataseed.bnbchain.org"
CHAIN_ID = 56
PRICE_RAW = 100_000_000_000_000_000
COMMERCE = to_checksum_address("0xea4daa3100a767e86fded867729ae7446476eba6")
ROUTER = to_checksum_address("0x51895229e12f9876011789b04f8698af06ccd6da")
POLICY = to_checksum_address("0x9c01845705b3078aa2e8cff7520a6376fd766de5")
U_TOKEN = to_checksum_address("0xce24439f2d9c6a2289f741120fe202248b666666")
STATUS_NAMES = ("OPEN", "FUNDED", "SUBMITTED", "COMPLETED", "REJECTED", "EXPIRED")
VERDICT_NAMES = ("UNDECIDED", "APPROVE", "REJECT")
ADDRESS_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")
ALLOWED_SKILLS = {
    "rebalance_plan",
    "grid_plan",
    "yield_plan",
    "health_factor",
}


def _call_data(signature: str, types: list[str], values: list[Any]) -> str:
    return f"0x{(keccak(text=signature)[:4] + encode(types, values)).hex()}"


def _number(
    raw: Any,
    *,
    field: str,
    minimum: float,
    maximum: float,
) -> float:
    if isinstance(raw, bool):
        raise TypeError(f"{field} must be a number")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a number") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def _address(raw: Any, *, field: str) -> str:
    value = str(raw).strip()
    if not ADDRESS_PATTERN.fullmatch(value):
        raise ValueError(f"{field} must be an EVM address")
    return to_checksum_address(value)


def validate_task_input(skill_id: str, raw: Any) -> dict[str, Any]:
    if skill_id not in ALLOWED_SKILLS:
        raise ValueError("skill_id is not an approved live-market service")
    if not isinstance(raw, dict):
        raise TypeError("task_input must be a JSON object")
    encoded = json.dumps(raw, separators=(",", ":"), ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 8_000:
        raise ValueError("task_input is too large")

    if skill_id == "health_factor":
        if set(raw) != {"address"}:
            raise ValueError("health_factor accepts only address")
        return {"address": _address(raw["address"], field="address")}

    if skill_id == "grid_plan":
        allowed = {"token", "capitalUsd", "levels", "bandPct"}
        if set(raw) - allowed or "token" not in raw:
            raise ValueError("grid_plan requires token and accepts capitalUsd, levels and bandPct")
        result: dict[str, Any] = {"token": _address(raw["token"], field="token")}
        if "capitalUsd" in raw:
            result["capitalUsd"] = _number(
                raw["capitalUsd"], field="capitalUsd", minimum=1, maximum=10_000_000
            )
        if "levels" in raw:
            levels = _number(raw["levels"], field="levels", minimum=2, maximum=200)
            if not levels.is_integer():
                raise ValueError("levels must be a whole number")
            result["levels"] = int(levels)
        if "bandPct" in raw:
            result["bandPct"] = _number(
                raw["bandPct"], field="bandPct", minimum=0.1, maximum=80
            )
        return result

    if skill_id == "yield_plan":
        allowed = {"amountUsd", "from", "currentApyPct"}
        if set(raw) - allowed:
            raise ValueError("yield_plan accepts amountUsd, from and currentApyPct")
        result = {}
        if "amountUsd" in raw:
            result["amountUsd"] = _number(
                raw["amountUsd"], field="amountUsd", minimum=1, maximum=100_000_000
            )
        if "from" in raw:
            current_market = str(raw["from"]).strip()
            if not current_market or len(current_market) > 120:
                raise ValueError("from must name a current Venus market")
            result["from"] = current_market
        if "currentApyPct" in raw:
            result["currentApyPct"] = _number(
                raw["currentApyPct"], field="currentApyPct", minimum=0, maximum=10_000
            )
        return result

    allowed = {"holdings", "targets"}
    if set(raw) - allowed or "holdings" not in raw:
        raise ValueError("rebalance_plan requires holdings and optionally accepts targets")
    holdings = raw["holdings"]
    if not isinstance(holdings, list) or not 2 <= len(holdings) <= 20:
        raise ValueError("holdings must contain between 2 and 20 positions")
    normalized_holdings: list[dict[str, Any]] = []
    tokens: set[str] = set()
    for index, item in enumerate(holdings):
        if not isinstance(item, dict) or set(item) != {"token", "usd"}:
            raise ValueError(f"holdings[{index}] must contain token and usd")
        token = _address(item["token"], field=f"holdings[{index}].token")
        if token.lower() in tokens:
            raise ValueError("holdings must not repeat a token")
        tokens.add(token.lower())
        normalized_holdings.append(
            {
                "token": token,
                "usd": _number(
                    item["usd"], field=f"holdings[{index}].usd", minimum=0.01, maximum=100_000_000
                ),
            }
        )
    result = {"holdings": normalized_holdings}
    if "targets" in raw:
        targets = raw["targets"]
        if not isinstance(targets, dict) or not targets:
            raise ValueError("targets must be a non-empty token-to-percent map")
        normalized_targets: dict[str, float] = {}
        for token_raw, percent_raw in targets.items():
            token = _address(token_raw, field="targets token")
            if token.lower() not in tokens:
                raise ValueError("every target token must also appear in holdings")
            normalized_targets[token] = _number(
                percent_raw, field=f"targets[{token}]", minimum=0, maximum=100
            )
        total = sum(normalized_targets.values())
        if not 99.5 <= total <= 100.5:
            raise ValueError("target percentages must total 100")
        result["targets"] = normalized_targets
    return result


async def _rpc(method: str, params: list[Any]) -> Any:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            BSC_MAINNET_RPC,
            json={"jsonrpc": "2.0", "id": method, "method": method, "params": params},
        )
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error") or "result" not in payload:
        raise ValueError(f"BSC mainnet rejected {method}")
    return payload["result"]


def _verified_quote(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    agent = raw.get("agent")
    quote = raw.get("quote")
    if not isinstance(agent, dict) or not isinstance(quote, dict):
        raise TypeError("live Agent quote is incomplete")
    if int(quote.get("chain_id", 0)) != CHAIN_ID:
        raise ValueError("live Agent quote is not for BSC mainnet")
    if to_checksum_address(str(quote.get("verifying_contract"))) != COMMERCE:
        raise ValueError("live Agent quote names an unexpected ERC-8183 contract")
    if to_checksum_address(str(quote.get("payment_token"))) != U_TOKEN:
        raise ValueError("live Agent quote names an unexpected payment token")
    if int(quote.get("price", 0)) != PRICE_RAW:
        raise ValueError("live Agent quote is not exactly 0.10 U")
    provider = _address(quote.get("provider"), field="provider")
    return agent, {**quote, "provider": provider}


async def prepare_live_hire(
    project_root: Path,
    *,
    buyer: str,
    skill_id: str,
    task_input: dict[str, Any],
) -> dict[str, Any]:
    owner = _address(buyer, field="buyer")
    normalized_input = validate_task_input(skill_id, task_input)
    quote_payload = await request_live_agent_quote(project_root, skill_id=skill_id)
    agent, quote = _verified_quote(quote_payload)
    now = int(time.time())
    expires_at = now + 60 * 60
    description_payload = {
        "schema_version": "safehire-live-hire-v1",
        "service": skill_id,
        "task_input": normalized_input,
        "erc8004_token_id": agent.get("erc8004_token_id"),
        "provider": quote["provider"],
        "price_raw": str(PRICE_RAW),
        "quote_observed_at": quote_payload.get("observed_at"),
        "created_at": datetime.now(UTC).isoformat(),
        "expires_at": expires_at,
    }
    description = json.dumps(description_payload, separators=(",", ":"), ensure_ascii=False)
    return {
        "schema_version": "1.0",
        "network": "bsc-mainnet",
        "chain_id": CHAIN_ID,
        "buyer": owner,
        "agent": agent,
        "quote": quote,
        "task_input": normalized_input,
        "expires_at": expires_at,
        "commerce_address": COMMERCE,
        "router_address": ROUTER,
        "policy_address": POLICY,
        "payment_token": U_TOKEN,
        "job_created_topic": (
            f"0x{keccak(text='JobCreated(uint256,address,address,address,uint256,address)').hex()}"
        ),
        "transaction": {
            "step": "create_job",
            "label": "Create external Agent job",
            "to": COMMERCE,
            "data": _call_data(
                "createJob(address,address,uint256,string,address)",
                ["address", "address", "uint256", "string", "address"],
                [quote["provider"], ROUTER, expires_at, description, ROUTER],
            ),
            "value": "0x0",
        },
        "safety": {
            "mainnet_value_at_risk": "0.10 U plus BNB gas",
            "exact_allowance": True,
            "unlimited_approval": False,
            "automatic_transaction": False,
            "manual_wallet_confirmation_per_write": True,
        },
    }


async def live_job_status(*, job_id: int) -> dict[str, Any]:
    if job_id <= 0:
        raise ValueError("job id is invalid")
    data = _call_data("getJob(uint256)", ["uint256"], [job_id])
    raw_result = await _rpc("eth_call", [{"to": COMMERCE, "data": data}, "latest"])
    raw = bytes.fromhex(str(raw_result)[2:])
    fields = decode(
        ["(uint256,address,address,address,string,uint256,uint256,uint8,address,uint256,bytes32)"],
        raw,
    )[0]
    status_value = int(fields[7])
    status_name = STATUS_NAMES[status_value] if status_value < len(STATUS_NAMES) else "UNKNOWN"
    expired = int(fields[6]) <= int(time.time())
    description_raw = str(fields[4])
    try:
        description = json.loads(description_raw)
    except json.JSONDecodeError:
        description = {"raw": description_raw}
    result: dict[str, Any] = {
        "chain_id": CHAIN_ID,
        "job_id": int(fields[0]),
        "client": to_checksum_address(fields[1]),
        "provider": to_checksum_address(fields[2]),
        "evaluator": to_checksum_address(fields[3]),
        "description": description,
        "budget_raw": str(fields[5]),
        "budget_u": str(Decimal(int(fields[5])) / Decimal(10**18)),
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
            "params": [{"to": POLICY, "data": call_data}, "latest"],
        }
        for index, (_, call_data) in enumerate(policy_calls, start=1)
    ]
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(BSC_MAINNET_RPC, json=batch)
        response.raise_for_status()
        policy_payload = response.json()
    if not isinstance(policy_payload, list):
        raise TypeError("BSC mainnet policy read returned an unexpected response")
    responses = {int(item.get("id", 0)): item for item in policy_payload if isinstance(item, dict)}
    if len(responses) != len(policy_calls):
        raise ValueError("BSC mainnet policy read returned an incomplete batch")
    for index, (name, _) in enumerate(policy_calls, start=1):
        item = responses[index]
        if item.get("error"):
            raise ValueError(f"BSC mainnet policy {name} read failed")

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
    verdict_name = (
        VERDICT_NAMES[verdict_value] if verdict_value < len(VERDICT_NAMES) else "UNKNOWN"
    )
    result.update(
        {
            "can_settle": verdict_value in {1, 2},
            "policy_verdict": verdict_name,
            "policy_reason": f"0x{reason.hex()}",
            "policy_submitted_at": policy_submitted_at,
            "dispute_window_seconds": dispute_window,
            "settle_after": settle_after,
            "seconds_until_settle": max(0, settle_after - int(time.time())),
            "disputed": disputed,
        }
    )
    return result


async def live_followup_plan(
    *,
    buyer: str,
    skill_id: str,
    job_id: int,
) -> dict[str, Any]:
    owner = _address(buyer, field="buyer")
    status = await live_job_status(job_id=job_id)
    if status["client"].lower() != owner.lower():
        raise ValueError("the connected wallet does not own this job")
    description = status.get("description")
    if not isinstance(description, dict) or description.get("service") != skill_id:
        raise ValueError("the job description does not match the selected service")
    if str(description.get("provider", "")).lower() != status["provider"].lower():
        raise ValueError("the on-chain provider does not match the verified job description")
    if str(description.get("price_raw", "")) != str(PRICE_RAW):
        raise ValueError("the verified job description is not priced at exactly 0.10 U")
    if status["status"] != "OPEN":
        raise ValueError(f"job #{job_id} is {str(status['status']).lower()}, not open")
    return {
        "chain_id": CHAIN_ID,
        "job_id": job_id,
        "price_raw": str(PRICE_RAW),
        "payment_token": U_TOKEN,
        "commerce_address": COMMERCE,
        "transactions": [
            {
                "step": "register_job",
                "label": "Bind official optimistic policy",
                "to": ROUTER,
                "data": _call_data(
                    "registerJob(uint256,address)", ["uint256", "address"], [job_id, POLICY]
                ),
                "value": "0x0",
            },
            {
                "step": "set_budget",
                "label": "Set exact 0.10 U budget",
                "to": COMMERCE,
                "data": _call_data(
                    "setBudget(uint256,uint256,bytes)",
                    ["uint256", "uint256", "bytes"],
                    [job_id, PRICE_RAW, b""],
                ),
                "value": "0x0",
            },
            {
                "step": "approve_u",
                "label": "Approve exactly 0.10 U",
                "to": U_TOKEN,
                "data": _call_data(
                    "approve(address,uint256)", ["address", "uint256"], [COMMERCE, PRICE_RAW]
                ),
                "value": "0x0",
            },
            {
                "step": "fund_job",
                "label": "Fund 0.10 U escrow",
                "to": COMMERCE,
                "data": _call_data(
                    "fund(uint256,uint256,bytes)",
                    ["uint256", "uint256", "bytes"],
                    [job_id, PRICE_RAW, b""],
                ),
                "value": "0x0",
            },
        ],
    }


async def notify_live_agent(
    *,
    job_id: int,
    skill_id: str,
) -> dict[str, Any]:
    status = await live_job_status(job_id=job_id)
    if status["status"] not in {"FUNDED", "SUBMITTED", "COMPLETED"}:
        raise ValueError(f"job #{job_id} must be funded before Agent notification")
    if status["budget_raw"] != str(PRICE_RAW):
        raise ValueError("funded job budget is not exactly 0.10 U")
    description = status.get("description")
    if not isinstance(description, dict) or description.get("service") != skill_id:
        raise ValueError("funded job does not match the requested service")
    if str(description.get("provider", "")).lower() != status["provider"].lower():
        raise ValueError("funded job provider does not match the verified job description")
    if str(description.get("price_raw", "")) != str(PRICE_RAW):
        raise ValueError("funded job description is not priced at exactly 0.10 U")
    task_input = validate_task_input(skill_id, description.get("task_input"))
    data = {
        "skill": "notify_funded",
        "service": skill_id,
        "job_id": job_id,
        "parameters": task_input,
        **task_input,
    }
    request = {
        "jsonrpc": "2.0",
        "id": f"safehire-funded-{job_id}",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": f"safehire-funded-{job_id}",
                "parts": [{"kind": "data", "data": data}],
            }
        },
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(A2A_ENDPOINT, json=request)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("external Agent rejected the funded-job notification")
    return {
        "job_id": job_id,
        "skill_id": skill_id,
        "notified_at": datetime.now(UTC).isoformat(),
        "agent_response": payload.get("result"),
        "next_action": "wait_for_onchain_submission_then_review",
        "transaction_sent": False,
    }


async def live_settle_plan(*, job_id: int) -> dict[str, Any]:
    status = await live_job_status(job_id=job_id)
    if status["completed"]:
        raise ValueError(f"job #{job_id} is already completed")
    if status["status"] != "SUBMITTED":
        raise ValueError(f"job #{job_id} is {str(status['status']).lower()}, not submitted")
    if not status["can_settle"]:
        seconds = int(status.get("seconds_until_settle", 0))
        if seconds > 0:
            raise ValueError(f"delivery review window remains open for {seconds} seconds")
        raise ValueError("the policy has not returned a final verdict")
    verdict = str(status.get("policy_verdict", "APPROVE"))
    return {
        "job_id": job_id,
        "policy_verdict": verdict,
        "transaction": {
            "step": "settle_job",
            "label": (
                "Settle verified delivery and release 0.10 U"
                if verdict == "APPROVE"
                else "Finalize rejection and return escrow"
            ),
            "to": ROUTER,
            "data": _call_data("settle(uint256,bytes)", ["uint256", "bytes"], [job_id, b""]),
            "value": "0x0",
        },
    }


async def live_refund_plan(*, job_id: int) -> dict[str, Any]:
    status = await live_job_status(job_id=job_id)
    if not status["can_refund"]:
        raise ValueError(f"job #{job_id} is not eligible for an expired escrow refund")
    return {
        "job_id": job_id,
        "transaction": {
            "step": "refund_job",
            "label": "Refund expired 0.10 U escrow",
            "to": COMMERCE,
            "data": _call_data("claimRefund(uint256)", ["uint256"], [job_id]),
            "value": "0x0",
        },
    }
