from __future__ import annotations

import asyncio
import ipaddress
import json
import socket
import time
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeAlias
from urllib.parse import urljoin, urlparse

import httpx
from eth_abi.abi import decode, encode
from eth_utils.address import to_checksum_address
from eth_utils.crypto import keccak

from proofops.integrations.erc8183_quote import (
    canonical_json,
    verify_job_description,
)
from proofops.services.live_agent_market import (
    DEFAULT_A2A_ENDPOINT,
    request_live_agent_quote,
    resolve_live_agent,
)

BSC_MAINNET_RPC = "https://bsc-dataseed.bnbchain.org"
CHAIN_ID = 56
PRICE_RAW = 100_000_000_000_000_000
COMMERCE = to_checksum_address("0xea4daa3100a767e86fded867729ae7446476eba6")
ROUTER = to_checksum_address("0x51895229e12f9876011789b04f8698af06ccd6da")
POLICY = to_checksum_address("0x9c01845705b3078aa2e8cff7520a6376fd766de5")
U_TOKEN = to_checksum_address("0xce24439f2d9c6a2289f741120fe202248b666666")
ZERO_ADDRESS = to_checksum_address("0x0000000000000000000000000000000000000000")
STATUS_NAMES = ("OPEN", "FUNDED", "SUBMITTED", "COMPLETED", "REJECTED", "EXPIRED")
VERDICT_NAMES = ("UNDECIDED", "APPROVE", "REJECT")
ALLOWED_SKILLS = {
    "rebalance_plan",
    "grid_plan",
    "yield_plan",
    "health_factor",
}
MAX_JOB_LIFETIME_SECONDS = 7 * 24 * 60 * 60
MIN_DELIVERY_SECONDS = 120
EXPIRY_BUFFER_SECONDS = 30 * 60
MANIFEST_MAX_BYTES = 1_000_000
LOG_SCAN_WINDOW = 10_000
LOG_SCAN_WINDOWS = 30
JOB_INITIALISED_TOPIC = f"0x{keccak(text='JobInitialised(uint256,bytes32,uint64,bytes)').hex()}"
JOB_COMPLETED_TOPIC = f"0x{keccak(text='JobCompleted(uint256,address,bytes32)').hex()}"
TRANSFER_TOPIC = f"0x{keccak(text='Transfer(address,address,uint256)').hex()}"

RpcCall: TypeAlias = Callable[[str, list[Any]], Awaitable[Any]]
ManifestFetcher: TypeAlias = Callable[[str, int], Awaitable[tuple[dict[str, Any], str]]]


def _call_data(signature: str, types: list[str], values: list[Any]) -> str:
    return f"0x{(keccak(text=signature)[:4] + encode(types, values)).hex()}"


def _decode_uint(raw: Any, *, field: str) -> int:
    value = str(raw or "")
    if not value.startswith("0x"):
        raise ValueError(f"{field} returned malformed hex")
    return int.from_bytes(bytes.fromhex(value[2:]), byteorder="big")


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
    try:
        return to_checksum_address(str(raw).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an EVM address") from exc


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
                    item["usd"],
                    field=f"holdings[{index}].usd",
                    minimum=0.01,
                    maximum=100_000_000,
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


async def _policy_dispute_window() -> int:
    raw = await _rpc(
        "eth_call",
        [{"to": POLICY, "data": _call_data("disputeWindow()", [], [])}, "latest"],
    )
    window = _decode_uint(raw, field="disputeWindow")
    if not 1 <= window <= 7 * 24 * 60 * 60:
        raise ValueError("policy dispute window is outside the supported safety range")
    return window


def _parse_task_spec(description: Mapping[str, Any]) -> dict[str, Any]:
    if description.get("version") != 1:
        raise ValueError("job does not contain the supported signed description version")
    raw_task = description.get("task")
    if not isinstance(raw_task, str):
        raise TypeError("signed job description contains no task")
    try:
        task = json.loads(raw_task)
    except json.JSONDecodeError as exc:
        raise ValueError("signed job task is not valid JSON") from exc
    if not isinstance(task, dict) or task.get("schema_version") != "safehire-external-hire-v2":
        raise ValueError("job was not created by the hardened SafeHire hire flow")
    skill_id = str(task.get("service", ""))
    token_id = task.get("erc8004_token_id")
    nonce = str(task.get("request_nonce", ""))
    if skill_id not in ALLOWED_SKILLS:
        raise ValueError("signed job names an unsupported service")
    if not isinstance(token_id, int) or token_id <= 0:
        raise ValueError("signed job has no valid ERC-8004 token id")
    if len(nonce) < 16 or len(nonce) > 128:
        raise ValueError("signed job request nonce is invalid")
    task_input = validate_task_input(skill_id, task.get("task_input"))
    return {
        "schema_version": task["schema_version"],
        "service": skill_id,
        "erc8004_token_id": token_id,
        "request_nonce": nonce,
        "task_input": task_input,
    }


async def _verify_anchored_description(
    description: Mapping[str, Any], *, provider: str
) -> dict[str, Any]:
    return await verify_job_description(
        description=description,
        provider=provider,
        expected_chain_id=CHAIN_ID,
        expected_verifying_contract=COMMERCE,
        expected_payment_token=U_TOKEN,
        expected_price_raw=PRICE_RAW,
        rpc_url=BSC_MAINNET_RPC,
        rpc_call=_rpc,
    )


async def prepare_live_hire(
    project_root: Path,
    *,
    buyer: str,
    skill_id: str,
    task_input: dict[str, Any],
    agent_token_id: int | None = None,
) -> dict[str, Any]:
    """Prepare one unsigned createJob call from a verified provider promise."""

    owner = _address(buyer, field="buyer")
    normalized_input = validate_task_input(skill_id, task_input)
    quote_payload = await request_live_agent_quote(
        project_root,
        skill_id=skill_id,
        agent_token_id=agent_token_id,
        task_input=normalized_input,
        rpc_url=BSC_MAINNET_RPC,
        rpc_call=_rpc,
    )
    verification = quote_payload.get("quote_verification")
    quote = quote_payload.get("quote")
    if not isinstance(verification, dict) or not isinstance(quote, dict):
        raise TypeError("verified quote response is incomplete")
    provider = _address(verification.get("provider"), field="provider")
    job_description = str(verification.get("job_description") or "")
    if not job_description:
        raise ValueError("verified quote has no signed job description")

    dispute_window = await _policy_dispute_window()
    eta = int(verification.get("estimated_completion_seconds") or 0)
    now = int(time.time())
    lifetime = max(eta, MIN_DELIVERY_SECONDS) + dispute_window + EXPIRY_BUFFER_SECONDS
    if lifetime > MAX_JOB_LIFETIME_SECONDS:
        raise ValueError("provider ETA and dispute window exceed the supported job lifetime")
    expires_at = now + lifetime
    quote_expires_at = int(verification.get("quote_expires_at") or 0)
    if quote_expires_at <= now + 30:
        raise ValueError("signed quote expires too soon to create a safe job")

    return {
        "schema_version": "2.0",
        "network": "bsc-mainnet",
        "chain_id": CHAIN_ID,
        "buyer": owner,
        "agent": quote_payload.get("agent"),
        "quote": quote,
        "quote_verification": verification,
        "task_input": normalized_input,
        "expires_at": expires_at,
        "commerce_address": COMMERCE,
        "router_address": ROUTER,
        "policy_address": POLICY,
        "payment_token": U_TOKEN,
        "job_created_topic": (
            f"0x{keccak(text='JobCreated(uint256,address,address,address,uint256,address)').hex()}"
        ),
        "timeline": {
            "quote_expires_at": quote_expires_at,
            "estimated_completion_seconds": eta,
            "dispute_window_seconds": dispute_window,
            "safety_buffer_seconds": EXPIRY_BUFFER_SECONDS,
            "job_expires_at": expires_at,
        },
        "transaction": {
            "step": "create_job",
            "label": "Create signed external Agent job",
            "to": COMMERCE,
            "data": _call_data(
                "createJob(address,address,uint256,string,address)",
                ["address", "address", "uint256", "string", "address"],
                [provider, ROUTER, expires_at, job_description, ROUTER],
            ),
            "value": "0x0",
            "valid_until": quote_expires_at,
        },
        "safety": {
            "mainnet_value_at_risk": "0.10 U plus BNB gas",
            "exact_allowance": True,
            "unlimited_approval": False,
            "automatic_transaction": False,
            "manual_wallet_confirmation_per_write": True,
            "signed_task_bound": True,
            "cross_chain_replay_blocked": True,
        },
    }


async def _open_job_progress(client: str, job_id: int) -> dict[str, Any]:
    calls = [
        _rpc(
            "eth_call",
            [{"to": ROUTER, "data": _call_data("jobPolicy(uint256)", ["uint256"], [job_id])}, "latest"],
        ),
        _rpc(
            "eth_call",
            [
                {
                    "to": U_TOKEN,
                    "data": _call_data(
                        "allowance(address,address)",
                        ["address", "address"],
                        [client, COMMERCE],
                    ),
                },
                "latest",
            ],
        ),
    ]
    raw_policy, raw_allowance = await asyncio.gather(*calls)
    policy_bytes = bytes.fromhex(str(raw_policy)[2:])
    if len(policy_bytes) < 32:
        raise ValueError("router jobPolicy returned malformed data")
    job_policy = to_checksum_address(policy_bytes[-20:])
    allowance = _decode_uint(raw_allowance, field="allowance")
    return {
        "registered_policy": job_policy,
        "policy_registered": job_policy == POLICY,
        "allowance_raw": str(allowance),
        "exact_allowance": allowance == PRICE_RAW,
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
    if int(fields[0]) != job_id:
        raise ValueError("BSC returned a different job id")
    status_value = int(fields[7])
    status_name = STATUS_NAMES[status_value] if status_value < len(STATUS_NAMES) else "UNKNOWN"
    now = int(time.time())
    expired = int(fields[6]) <= now
    description_raw = str(fields[4])
    try:
        description = json.loads(description_raw)
    except json.JSONDecodeError as exc:
        raise ValueError("job description is not the signed SafeHire schema") from exc
    if not isinstance(description, dict):
        raise TypeError("job description is not an object")
    provider = to_checksum_address(fields[2])
    task_spec = _parse_task_spec(description)
    description_verification = await _verify_anchored_description(
        description, provider=provider
    )
    result: dict[str, Any] = {
        "chain_id": CHAIN_ID,
        "job_id": int(fields[0]),
        "client": to_checksum_address(fields[1]),
        "provider": provider,
        "evaluator": to_checksum_address(fields[3]),
        "description": description,
        "task_spec": task_spec,
        "description_verification": description_verification,
        "budget_raw": str(fields[5]),
        "budget_u": str(Decimal(int(fields[5])) / Decimal(10**18)),
        "expired_at": int(fields[6]),
        "status": status_name,
        "status_value": status_value,
        "submitted_at": int(fields[9]),
        "deliverable_hash": f"0x{fields[10].hex()}",
        "can_settle": False,
        "can_dispute": False,
        "completed": status_value == 3,
        "expired": expired,
        "can_refund": status_value == 1 and expired,
    }
    if status_value == 0:
        result["open_progress"] = await _open_job_progress(result["client"], job_id)
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
    seconds_until_settle = max(0, settle_after - now)
    review_window_closed = seconds_until_settle == 0
    verdict_name = (
        VERDICT_NAMES[verdict_value] if verdict_value < len(VERDICT_NAMES) else "UNKNOWN"
    )
    policy_final = verdict_name in {"APPROVE", "REJECT"}
    can_settle = policy_final and (
        verdict_name == "REJECT" or review_window_closed
    )
    result.update(
        {
            "can_settle": can_settle,
            "can_dispute": not disputed and not review_window_closed,
            "policy_final": policy_final,
            "policy_verdict": verdict_name,
            "policy_reason": f"0x{reason.hex()}",
            "policy_submitted_at": policy_submitted_at,
            "dispute_window_seconds": dispute_window,
            "settle_after": settle_after,
            "seconds_until_settle": seconds_until_settle,
            "review_window_closed": review_window_closed,
            "disputed": disputed,
        }
    )
    return result


async def live_followup_plan(*, buyer: str, job_id: int) -> dict[str, Any]:
    """Rebuild only the missing Open-state transactions from chain state."""

    owner = _address(buyer, field="buyer")
    status = await live_job_status(job_id=job_id)
    if status["client"].lower() != owner.lower():
        raise ValueError("the connected wallet does not own this job")
    if status["status"] != "OPEN":
        raise ValueError(f"job #{job_id} is {str(status['status']).lower()}, not open")
    progress = status.get("open_progress")
    if not isinstance(progress, dict):
        raise TypeError("open job progress is unavailable")
    registered_policy = _address(progress["registered_policy"], field="registered policy")
    if registered_policy not in {ZERO_ADDRESS, POLICY}:
        raise ValueError("job is already bound to an unexpected policy")
    budget = int(status["budget_raw"])
    if budget not in {0, PRICE_RAW}:
        raise ValueError("job already has an unexpected budget")
    allowance = int(progress["allowance_raw"])

    transactions: list[dict[str, Any]] = []
    if registered_policy == ZERO_ADDRESS:
        transactions.append(
            {
                "step": "register_job",
                "label": "Bind official optimistic policy",
                "to": ROUTER,
                "data": _call_data(
                    "registerJob(uint256,address)", ["uint256", "address"], [job_id, POLICY]
                ),
                "value": "0x0",
            }
        )
    if budget == 0:
        transactions.append(
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
            }
        )
    if allowance != PRICE_RAW:
        transactions.append(
            {
                "step": "approve_u",
                "label": "Approve exactly 0.10 U",
                "to": U_TOKEN,
                "data": _call_data(
                    "approve(address,uint256)", ["address", "uint256"], [COMMERCE, PRICE_RAW]
                ),
                "value": "0x0",
            }
        )
    transactions.append(
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
        }
    )
    return {
        "chain_id": CHAIN_ID,
        "job_id": job_id,
        "task_spec": status["task_spec"],
        "description_verification": status["description_verification"],
        "price_raw": str(PRICE_RAW),
        "payment_token": U_TOKEN,
        "commerce_address": COMMERCE,
        "resume_safe": True,
        "transactions": transactions,
    }


async def notify_live_agent(project_root: Path, *, job_id: int) -> dict[str, Any]:
    status = await live_job_status(job_id=job_id)
    if status["status"] == "SUBMITTED":
        return {
            "job_id": job_id,
            "status": "already_submitted",
            "transaction_sent": False,
            "next_action": "review_delivery",
        }
    if status["status"] == "COMPLETED":
        return {
            "job_id": job_id,
            "status": "already_completed",
            "transaction_sent": False,
            "next_action": "download_verified_receipt",
        }
    if status["status"] != "FUNDED":
        raise ValueError(f"job #{job_id} must be funded before Agent notification")
    if status["budget_raw"] != str(PRICE_RAW):
        raise ValueError("funded job budget is not exactly 0.10 U")
    task_spec = status["task_spec"]
    assert isinstance(task_spec, dict)
    skill_id = str(task_spec["service"])
    token_id = int(task_spec["erc8004_token_id"])
    route = resolve_live_agent(
        project_root, skill_id=skill_id, agent_token_id=token_id
    )
    if str(route.get("operator", "")).strip() == "":
        raise ValueError("selected Agent has no operator identity")
    data = {
        "skill": "notify_funded",
        "service": skill_id,
        "job_id": job_id,
        "parameters": task_spec["task_input"],
        **task_spec["task_input"],
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
    endpoint = str(route.get("endpoint") or DEFAULT_A2A_ENDPOINT)
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(endpoint, json=request)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("external Agent rejected the funded-job notification")
    return {
        "job_id": job_id,
        "skill_id": skill_id,
        "erc8004_token_id": token_id,
        "operator": route.get("operator"),
        "endpoint": endpoint,
        "status": "accepted",
        "notified_at": datetime.now(UTC).isoformat(),
        "agent_response": payload.get("result"),
        "next_action": "wait_for_onchain_submission_then_review",
        "transaction_sent": False,
    }


def _topic_uint(value: int) -> str:
    return f"0x{value:064x}"


async def _find_event_log(*, address: str, topic0: str, job_id: int) -> dict[str, Any] | None:
    latest = int(str(await _rpc("eth_blockNumber", [])), 16)
    to_block = latest
    for _ in range(LOG_SCAN_WINDOWS):
        from_block = max(0, to_block - LOG_SCAN_WINDOW + 1)
        logs = await _rpc(
            "eth_getLogs",
            [
                {
                    "address": address,
                    "fromBlock": hex(from_block),
                    "toBlock": hex(to_block),
                    "topics": [topic0, _topic_uint(job_id)],
                }
            ],
        )
        if isinstance(logs, list) and logs:
            candidates = [item for item in logs if isinstance(item, dict)]
            if candidates:
                return candidates[-1]
        if from_block == 0:
            break
        to_block = from_block - 1
    return None


async def _delivery_pointer(job_id: int, expected_hash: str) -> dict[str, Any]:
    log = await _find_event_log(
        address=POLICY, topic0=JOB_INITIALISED_TOPIC, job_id=job_id
    )
    if log is None:
        raise ValueError("JobInitialised delivery event was not found in the recent chain window")
    raw_data = bytes.fromhex(str(log.get("data", "0x"))[2:])
    deliverable, submitted_at, opt_params = decode(["bytes32", "uint64", "bytes"], raw_data)
    deliverable_hash = f"0x{deliverable.hex()}"
    if deliverable_hash.lower() != expected_hash.lower():
        raise ValueError("policy delivery event hash does not match the Commerce job")
    try:
        params = json.loads(bytes(opt_params).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("delivery event optParams is not valid JSON") from exc
    if not isinstance(params, dict) or not isinstance(params.get("deliverable_url"), str):
        raise TypeError("delivery event contains no deliverable_url")
    return {
        "deliverable_url": params["deliverable_url"],
        "deliverable_hash": deliverable_hash,
        "submitted_at": int(submitted_at),
        "block_number": int(str(log.get("blockNumber", "0x0")), 16),
        "transaction_hash": str(log.get("transactionHash") or ""),
    }


def _normalise_manifest_url(raw: str) -> str:
    value = raw.strip()
    if value.startswith("ipfs://"):
        cid_path = value.removeprefix("ipfs://").lstrip("/")
        if not cid_path or ".." in cid_path.split("/"):
            raise ValueError("deliverable IPFS URL is invalid")
        return f"https://ipfs.io/ipfs/{cid_path}"
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("deliverable URL must use HTTPS or ipfs://")
    return value


def _public_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


async def _assert_public_hostname(hostname: str) -> None:
    try:
        direct = ipaddress.ip_address(hostname)
    except ValueError:
        direct = None
    if direct is not None:
        if not _public_ip(str(direct)):
            raise ValueError("deliverable URL resolves to a non-public IP")
        return
    try:
        rows = await asyncio.to_thread(socket.getaddrinfo, hostname, 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("deliverable hostname cannot be resolved") from exc
    addresses = {str(row[4][0]) for row in rows}
    if not addresses or not all(_public_ip(address) for address in addresses):
        raise ValueError("deliverable hostname resolves to a non-public IP")


async def _fetch_manifest(url: str, max_bytes: int) -> tuple[dict[str, Any], str]:
    current = _normalise_manifest_url(url)
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for _ in range(3):
            parsed = urlparse(current)
            assert parsed.hostname is not None
            await _assert_public_hostname(parsed.hostname)
            async with client.stream("GET", current, headers={"Accept": "application/json"}) as response:
                if 300 <= response.status_code < 400:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("deliverable redirect has no location")
                    current = _normalise_manifest_url(urljoin(current, location))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";", 1)[0]
                if content_type not in {"application/json", "text/json", "text/plain"}:
                    raise ValueError("deliverable response is not JSON")
                buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > max_bytes:
                        raise ValueError("deliverable manifest exceeds the configured size limit")
            try:
                payload = json.loads(buffer.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("deliverable manifest is not valid UTF-8 JSON") from exc
            if not isinstance(payload, dict):
                raise TypeError("deliverable manifest must be a JSON object")
            return payload, current
    raise ValueError("deliverable redirect limit exceeded")


def _verify_manifest(
    manifest: Mapping[str, Any], *, job_id: int, expected_hash: str
) -> dict[str, Any]:
    if manifest.get("version") != 1:
        raise ValueError("deliverable manifest uses an unsupported version")
    if manifest.get("job_id") != job_id or manifest.get("chain_id") != CHAIN_ID:
        raise ValueError("deliverable manifest is bound to a different job or chain")
    contracts = manifest.get("contracts")
    response = manifest.get("response")
    if not isinstance(contracts, Mapping) or not isinstance(response, Mapping):
        raise TypeError("deliverable manifest is missing contracts or response")
    expected_contracts = {"commerce": COMMERCE, "router": ROUTER, "policy": POLICY}
    for name, expected in expected_contracts.items():
        if _address(contracts.get(name), field=f"manifest contracts.{name}") != expected:
            raise ValueError(f"deliverable manifest {name} contract mismatch")
    content = response.get("content")
    content_type = response.get("content_type")
    if not isinstance(content, str) or not content.strip():
        raise ValueError("deliverable manifest contains no response content")
    if not isinstance(content_type, str) or not content_type.strip():
        raise ValueError("deliverable manifest contains no response content_type")
    computed_hash = f"0x{keccak(text=canonical_json(dict(manifest))).hex()}"
    if computed_hash.lower() != expected_hash.lower():
        raise ValueError("deliverable manifest hash does not match the on-chain commitment")
    return {
        "valid": True,
        "computed_hash": computed_hash,
        "content": content,
        "content_type": content_type,
        "metadata": manifest.get("metadata") if isinstance(manifest.get("metadata"), Mapping) else {},
    }


async def live_delivery(
    *,
    job_id: int,
    fetch_manifest: ManifestFetcher | None = None,
) -> dict[str, Any]:
    status = await live_job_status(job_id=job_id)
    if status["status"] not in {"SUBMITTED", "COMPLETED"}:
        raise ValueError(f"job #{job_id} has no submitted delivery")
    pointer = await _delivery_pointer(job_id, str(status["deliverable_hash"]))
    fetcher = fetch_manifest or _fetch_manifest
    manifest, resolved_url = await fetcher(pointer["deliverable_url"], MANIFEST_MAX_BYTES)
    verification = _verify_manifest(
        manifest, job_id=job_id, expected_hash=str(status["deliverable_hash"])
    )
    terms = status["description"].get("terms")
    return {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "chain_id": CHAIN_ID,
        "job_id": job_id,
        "provider": status["provider"],
        "task_spec": status["task_spec"],
        "success_criteria": terms.get("success_criteria", []) if isinstance(terms, dict) else [],
        "onchain": pointer,
        "manifest_url": resolved_url,
        "manifest": manifest,
        "verification": {
            "hash_matches": True,
            "job_matches": True,
            "chain_matches": True,
            "contracts_match": True,
            "provider_submit_authorized_by_contract": True,
            "human_success_criteria_review_required": True,
            **verification,
        },
        "settlement": {
            "can_settle": status.get("can_settle", False),
            "can_dispute": status.get("can_dispute", False),
            "review_window_closed": status.get("review_window_closed", False),
            "seconds_until_settle": status.get("seconds_until_settle", 0),
            "policy_verdict": status.get("policy_verdict"),
            "disputed": status.get("disputed", False),
        },
        "evidence_boundary": (
            "SafeHire verified the retrieved manifest against the on-chain deliverable hash, job, "
            "chain and contract trio. A human still decides whether the content satisfies the signed "
            "success criteria before settle or dispute."
        ),
    }


async def live_dispute_plan(*, buyer: str, job_id: int) -> dict[str, Any]:
    owner = _address(buyer, field="buyer")
    status = await live_job_status(job_id=job_id)
    if status["client"].lower() != owner.lower():
        raise ValueError("only the job client can dispute this delivery")
    if status["status"] != "SUBMITTED" or not status.get("can_dispute"):
        raise ValueError("delivery is not inside an open dispute window")
    return {
        "job_id": job_id,
        "seconds_remaining": status.get("seconds_until_settle", 0),
        "transaction": {
            "step": "dispute_job",
            "label": "Dispute delivery before the review window closes",
            "to": POLICY,
            "data": _call_data("dispute(uint256)", ["uint256"], [job_id]),
            "value": "0x0",
        },
        "boundary": (
            "Disputing does not itself reject the job. It opens the policy's voter path and blocks "
            "silent approval until the policy reaches a final verdict."
        ),
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
    verdict = str(status.get("policy_verdict", "UNDECIDED"))
    if verdict not in {"APPROVE", "REJECT"}:
        raise ValueError("policy verdict is not final")
    return {
        "job_id": job_id,
        "policy_verdict": verdict,
        "review_window_closed": status.get("review_window_closed"),
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


def _topic_address(value: str) -> str:
    return f"0x{_address(value, field='event address')[2:].lower():0>64}"


async def _verified_payment(settlement_tx_hash: str, *, provider: str) -> int | None:
    receipt = await _rpc("eth_getTransactionReceipt", [settlement_tx_hash])
    if not isinstance(receipt, Mapping) or receipt.get("status") != "0x1":
        return None
    for raw in receipt.get("logs", []):
        if not isinstance(raw, Mapping):
            continue
        topics = raw.get("topics")
        if (
            str(raw.get("address", "")).lower() == U_TOKEN.lower()
            and isinstance(topics, list)
            and len(topics) >= 3
            and str(topics[0]).lower() == TRANSFER_TOPIC.lower()
            and str(topics[1]).lower() == _topic_address(COMMERCE).lower()
            and str(topics[2]).lower() == _topic_address(provider).lower()
        ):
            amount = int(str(raw.get("data", "0x0")), 16)
            if 0 < amount <= PRICE_RAW:
                return amount
    return None


async def build_verified_receipt(*, job_id: int) -> dict[str, Any]:
    """Build a server-revalidated mainnet dossier suitable for evidence capture."""

    status = await live_job_status(job_id=job_id)
    if status["status"] != "COMPLETED":
        raise ValueError("a paid evidence dossier requires a completed job")
    delivery = await live_delivery(job_id=job_id)
    completion = await _find_event_log(
        address=COMMERCE, topic0=JOB_COMPLETED_TOPIC, job_id=job_id
    )
    if completion is None:
        raise ValueError("JobCompleted settlement event was not found")
    settlement_tx_hash = str(completion.get("transactionHash") or "")
    payment_raw = await _verified_payment(
        settlement_tx_hash, provider=str(status["provider"])
    )
    if payment_raw is None:
        raise ValueError("provider payment transfer could not be verified")
    task_spec = status["task_spec"]
    assert isinstance(task_spec, dict)
    return {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "verification_status": "mainnet_verified",
        "verified_at": datetime.now(UTC).isoformat(),
        "chain_id": CHAIN_ID,
        "job_id": job_id,
        "external_provider": True,
        "provider": status["provider"],
        "client": status["client"],
        "erc8004_token_id": task_spec["erc8004_token_id"],
        "skill_id": task_spec["service"],
        "task_input": task_spec["task_input"],
        "quote": status["description_verification"],
        "delivery": {
            "manifest_url": delivery["manifest_url"],
            "deliverable_hash": status["deliverable_hash"],
            "manifest": delivery["manifest"],
            "verification": delivery["verification"],
        },
        "settlement_tx_hash": settlement_tx_hash,
        "settlement_block_number": int(str(completion.get("blockNumber", "0x0")), 16),
        "paid": True,
        "payment_token": U_TOKEN,
        "payment_raw": str(payment_raw),
        "quoted_price_raw": str(PRICE_RAW),
        "provider_payment_verified": True,
        "evidence_boundary": (
            "This dossier was rebuilt from BSC Mainnet state, the signed on-chain job description, "
            "the hash-matched delivery manifest and the settlement transfer. Save it under "
            "evidence/marketplace/paid-deliveries/ and commit it to make the track record public."
        ),
    }
