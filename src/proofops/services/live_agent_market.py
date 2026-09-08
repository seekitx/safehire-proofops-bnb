from __future__ import annotations

import asyncio
import json
import math
import secrets
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from proofops.integrations.erc8183_quote import (
    QuoteVerificationError,
    RpcCall,
    _default_rpc,
    canonical_json,
    find_named_value,
    find_negotiation_envelope,
    verify_negotiation_envelope,
)

DEFAULT_A2A_CARD_URL = "https://agent.brainonbnb.com/.well-known/agent-card.json"
DEFAULT_A2A_ENDPOINT = "https://agent.brainonbnb.com/a2a"
DEFAULT_BSC_MAINNET_RPC = "https://bsc-dataseed.bnbchain.org"
DEFAULT_COMMERCE = "0xea4daa3100a767e86fded867729ae7446476eba6"
DEFAULT_U_TOKEN = "0xce24439f2d9c6a2289f741120fe202248b666666"
DEFAULT_PRICE_RAW = 100_000_000_000_000_000
SCAN8004_BASE = "https://api.8004scan.io/api/v1"
TX_HASH_LENGTH = 66

# Backward-compatible aliases used by older imports and tests. Runtime routing
# no longer relies on these globals; each catalog item may name its own route.
A2A_CARD_URL = DEFAULT_A2A_CARD_URL
A2A_ENDPOINT = DEFAULT_A2A_ENDPOINT


def new_hire_pause(project_root: Path, token_id: int) -> str | None:
    path = project_root / "config/live-hire-pauses.json"
    if not path.exists():
        return None
    pauses = json.loads(path.read_text())
    reason = pauses.get(str(token_id))
    return str(reason) if reason else None


def _load_catalog(project_root: Path) -> dict[str, Any]:
    path = project_root / "evidence" / "marketplace" / "live-agent-catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("live BSC agent catalog is missing or malformed") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("agents"), list):
        raise TypeError("live BSC agent catalog has an unexpected schema")
    return payload


def _public_https(value: Any, *, field: str) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    hostname = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or not hostname
        or hostname in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
        or hostname.endswith(".local")
    ):
        raise ValueError(f"{field} must be a public HTTPS URL")
    return raw


def _provider_field(agent: dict[str, Any], catalog: dict[str, Any], name: str) -> Any:
    provider = agent.get("provider")
    if isinstance(provider, dict) and provider.get(name) is not None:
        return provider[name]
    if agent.get(name) is not None:
        return agent[name]
    return catalog.get(name)


def _agent_route(agent: dict[str, Any], catalog: dict[str, Any]) -> dict[str, str]:
    endpoint = _public_https(
        _provider_field(agent, catalog, "a2a_endpoint") or DEFAULT_A2A_ENDPOINT,
        field="agent a2a_endpoint",
    )
    card_url = _public_https(
        _provider_field(agent, catalog, "agent_card_url") or DEFAULT_A2A_CARD_URL,
        field="agent agent_card_url",
    )
    operator = str(
        _provider_field(agent, catalog, "operator") or catalog.get("operator") or "unknown"
    ).strip()
    return {"endpoint": endpoint, "agent_card_url": card_url, "operator": operator}


def _select_agent(
    catalog: dict[str, Any], *, skill_id: str, agent_token_id: int | None
) -> dict[str, Any]:
    candidates = [
        item
        for item in catalog["agents"]
        if isinstance(item, dict)
        and item.get("skill_id") == skill_id
        and (agent_token_id is None or int(item.get("token_id", 0)) == agent_token_id)
    ]
    if not candidates:
        raise ValueError("skill_id is not in the reviewed live BSC catalog")
    if len(candidates) > 1:
        raise ValueError("agent_token_id is required when multiple providers offer this skill")
    return candidates[0]


def resolve_live_agent(
    project_root: Path, *, skill_id: str, agent_token_id: int | None = None
) -> dict[str, Any]:
    """Return one reviewed catalog item with its independent provider route."""

    catalog = _load_catalog(project_root)
    selected = _select_agent(
        catalog, skill_id=skill_id, agent_token_id=agent_token_id
    )
    return {**selected, **_agent_route(selected, catalog)}


def _safe_number(raw: Any) -> float | None:
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
        return round(value, 3) if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _valid_tx_hash(raw: Any) -> bool:
    value = str(raw or "")
    return (
        len(value) == TX_HASH_LENGTH
        and value.startswith("0x")
        and all(character in "0123456789abcdefABCDEF" for character in value[2:])
    )


def _paid_delivery_counts(project_root: Path) -> Counter[int]:
    """Count only server-verifiable mainnet dossiers, never browser drafts."""

    counts: Counter[int] = Counter()
    directory = project_root / "evidence" / "marketplace" / "paid-deliveries"
    if not directory.is_dir():
        return counts
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        token_id = record.get("erc8004_token_id")
        if (
            record.get("evidence_mode") == "live"
            and record.get("verification_status") == "mainnet_verified"
            and record.get("chain_id") == 56
            and record.get("external_provider") is True
            and record.get("paid") is True
            and isinstance(token_id, int)
            and token_id > 0
            and _valid_tx_hash(record.get("settlement_tx_hash"))
        ):
            counts[token_id] += 1
    return counts


async def _index_signals(client: httpx.AsyncClient, token_id: int) -> dict[str, Any]:
    try:
        response = await client.get(f"{SCAN8004_BASE}/agents/56/{token_id}")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or str(payload.get("token_id", "")) != str(token_id):
            raise TypeError("unexpected Agent detail schema")
        health = payload.get("health_status")
        health = health if isinstance(health, dict) else {}
        services = health.get("services")
        services = services if isinstance(services, dict) else {}
        a2a = services.get("a2a")
        a2a = a2a if isinstance(a2a, dict) else {}
        return {
            "available": True,
            "source": "8004scan_official_api",
            "is_active": payload.get("is_active") is True,
            "is_verified": payload.get("is_verified") is True,
            "is_endpoint_verified": payload.get("is_endpoint_verified") is True,
            "index_health": health.get("overall_status"),
            "index_a2a_health": a2a.get("status"),
            "index_a2a_latency_ms": _safe_number(a2a.get("latency_ms")),
            "health_score": _safe_number(payload.get("health_score")),
            "quality_score": _safe_number(payload.get("quality_score")),
            "total_score": _safe_number(payload.get("total_score")),
            "metadata_completeness_score": _safe_number(
                payload.get("metadata_completeness_score")
            ),
            "total_feedbacks": int(payload.get("total_feedbacks") or 0),
            "total_validations": int(payload.get("total_validations") or 0),
            "successful_validations": int(payload.get("successful_validations") or 0),
            "owner_address": payload.get("owner_address"),
            "supported_protocols": payload.get("supported_protocols") or [],
            "supported_trust_models": payload.get("supported_trust_models") or [],
            "endpoint_last_checked_at": payload.get("endpoint_last_checked_at"),
            "updated_at": payload.get("updated_at"),
        }
    except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "available": False,
            "source": "8004scan_official_api",
            "error": type(exc).__name__,
        }


async def _probe_endpoint(endpoint: str) -> dict[str, Any]:
    request = {
        "jsonrpc": "2.0",
        "id": f"safehire-discovery-{secrets.token_hex(6)}",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": f"safehire-discovery-{secrets.token_hex(6)}",
                "parts": [{"kind": "data", "data": {"skill": "list"}}],
            }
        },
    }
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(endpoint, json=request)
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise TypeError("A2A list response returned no result object")
        services = result.get("services")
        if not isinstance(services, list) or result.get("can_sign") is not True:
            raise ValueError("A2A list response did not advertise signed hiring")
        service_map = {
            str(item["id"]): item
            for item in services
            if isinstance(item, dict) and isinstance(item.get("id"), str)
        }
        return {"reachable": True, "services": service_map, "error": None}
    except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"reachable": False, "services": {}, "error": type(exc).__name__}


async def live_agent_market(project_root: Path) -> dict[str, Any]:
    """Combine ERC-8004 identity, per-provider liveness and outcome evidence."""

    catalog = _load_catalog(project_root)
    observed_at = datetime.now(UTC).isoformat()
    catalog_agents = [item for item in catalog["agents"] if isinstance(item, dict)]
    routes = {
        int(item.get("token_id", 0)): _agent_route(item, catalog) for item in catalog_agents
    }
    endpoints = sorted({route["endpoint"] for route in routes.values()})
    async def probe_route(endpoint: str) -> dict[str, Any]:
        sdk_agent = next((item for item in catalog_agents if routes[int(item.get("token_id", 0))]["endpoint"] == endpoint
                          and _provider_field(item, catalog, "quote_format") == "bnbagent-sdk-v1"), None)
        if sdk_agent is None:
            return await _probe_endpoint(endpoint)
        try:
            quote = await request_live_agent_quote(project_root, skill_id=sdk_agent["skill_id"],
                                                  agent_token_id=int(sdk_agent["token_id"]))
            return {"reachable": True, "services": {sdk_agent["skill_id"]: {
                "id": sdk_agent["skill_id"], **quote["quote"], "signed_quote_verified": True}}, "error": None}
        except (ValueError, TypeError, KeyError, httpx.HTTPError, OSError) as exc:
            return {"reachable": False, "services": {}, "error": type(exc).__name__}
    probe_rows = await asyncio.gather(*(probe_route(endpoint) for endpoint in endpoints))
    probes = dict(zip(endpoints, probe_rows, strict=True))

    async with httpx.AsyncClient(timeout=10) as client:
        signal_rows = await asyncio.gather(
            *(
                _index_signals(client, int(item.get("token_id", 0)))
                for item in catalog_agents
            )
        )
    signals_by_token = {
        str(item.get("token_id")): signals
        for item, signals in zip(catalog_agents, signal_rows, strict=True)
    }
    paid_counts = _paid_delivery_counts(project_root)

    agents: list[dict[str, Any]] = []
    for item in catalog_agents:
        token_id = int(item.get("token_id", 0))
        route = routes[token_id]
        probe = probes[route["endpoint"]]
        skill_id = str(item.get("skill_id", ""))
        current = probe["services"].get(skill_id)
        market_signals = signals_by_token.get(str(token_id), {})
        callable_now = probe["reachable"] is True and current is not None
        indexed_a2a_health = market_signals.get("index_a2a_health")
        agents.append(
            {
                **item,
                "operator": route["operator"],
                "a2a_endpoint": route["endpoint"],
                "agent_card_url": route["agent_card_url"],
                "current_capability": current,
                "currently_callable": callable_now,
                "new_hire_paused_reason": new_hire_pause(project_root, token_id),
                "market_signals": market_signals,
                "signal_disagreement": (
                    "SafeHire reached this A2A service now, while the indexer's cached health is "
                    f"{indexed_a2a_health}. Both timestamps remain visible."
                    if callable_now and indexed_a2a_health not in {None, "healthy"}
                    else None
                ),
                "safehire_paid_deliveries": paid_counts[token_id],
            }
        )

    reachable_endpoints = sum(bool(probe["reachable"]) for probe in probes.values())
    operator_count = len({route["operator"] for route in routes.values() if route["operator"]})
    return {
        "source": "erc8004_snapshot_plus_per_provider_a2a_probe",
        "observed_at": observed_at,
        "registration_snapshot_observed_at": catalog.get("observed_at"),
        "endpoint_reachable": reachable_endpoints > 0,
        "endpoint_count": len(endpoints),
        "reachable_endpoint_count": reachable_endpoints,
        "operator_count": operator_count,
        "agents": agents,
        "trust_boundary": (
            "Each listing keeps its own ERC-8004 identity, operator and A2A route. "
            "Registration, current reachability, index signals and verified paid outcomes remain "
            "separate evidence dimensions; unavailable live evidence is never replaced by demo data."
        ),
    }


def _reviewed_request(
    *,
    selected: dict[str, Any],
    skill_id: str,
    task_input: dict[str, Any] | None,
    request_nonce: str,
    arena_task: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    token_id = int(selected.get("token_id", 0))
    if token_id <= 0:
        raise ValueError("selected Agent is missing a valid ERC-8004 token id")
    task_spec = {
        "schema_version": "safehire-external-hire-v2",
        "service": skill_id,
        "erc8004_token_id": token_id,
        "request_nonce": request_nonce,
        "task_input": task_input
        if task_input is not None
        else {
            "mode": "quote_preview",
            "note": "A fresh signed quote will bind the final task before any transaction plan.",
        },
    }
    if arena_task is not None:
        task_spec["arena_task"] = arena_task
    description = str(selected.get("description", "")).strip()
    request: dict[str, Any] = {
        "task_description": canonical_json(task_spec),
        "terms": {
            "deliverables": description,
            "quality_standards": (
                "Use current BNB Chain evidence, name sources and timestamps, disclose uncertainty, "
                "return a complete reviewable result, and never promise profit or move funds."
            ),
            "evaluation_required": True,
            "evaluator_type": "optimistic_policy",
            "success_criteria": [
                "Answer the selected SafeHire task and no unrelated task.",
                "Name material data sources and observation times or blocks.",
                "State risks, uncertainty and any condition that would change the recommendation.",
                "Return a self-contained deliverable suitable for independent review.",
            ],
        },
        "request_id": request_nonce,
    }
    if arena_task is not None:
        from proofops.arena.models import TaskSpec

        frozen_task = TaskSpec.model_validate(arena_task)
        request["terms"]["success_criteria"].append(
            "Deliver response.content as a safehire-proposal/2 JSON object for the exact arena_task: "
            f"agent_ref=56:{token_id}:{skill_id}, task_hash={frozen_task.task_hash}, "
            f"snapshot_hash={frozen_task.snapshot_hash}, with action and parameters. "
            "Use schema_version=safehire-proposal/2. Do not substitute narrative output. "
            "Do not accept these terms if this exact structured delivery is unsupported."
        )
    return request, task_spec


async def request_live_agent_quote(
    project_root: Path,
    *,
    skill_id: str,
    agent_token_id: int | None = None,
    task_input: dict[str, Any] | None = None,
    request_nonce: str | None = None,
    rpc_url: str = DEFAULT_BSC_MAINNET_RPC,
    rpc_call: RpcCall | None = None,
    arena_task: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify a complete signed commercial quote without signing or moving funds."""

    catalog = _load_catalog(project_root)
    selected = _select_agent(
        catalog, skill_id=skill_id, agent_token_id=agent_token_id
    )
    pause = new_hire_pause(project_root, int(selected["token_id"]))
    if pause:
        raise ValueError(pause)
    route = _agent_route(selected, catalog)
    quote_format = str(_provider_field(selected, catalog, "quote_format") or "safehire-v2")
    nonce = request_nonce or f"safehire-{secrets.token_hex(16)}"
    expected_request, task_spec = _reviewed_request(
        selected=selected,
        skill_id=skill_id,
        task_input=task_input,
        request_nonce=nonce,
        arena_task=arena_task,
    )
    if int(selected['token_id']) == 269224:
        from proofops.services.reviewed_grid import inputs
        if arena_task is not None:
            raise ValueError('ChainHelix requires its own grid task; do not reinterpret Arena inputs')
        normalized = inputs(task_input if task_input is not None else {'price': 750, 'budgetUsd': 1000, 'levels': 5, 'spanPct': 2})
        normalized['request_nonce'] = nonce
        task_spec = {'schema_version': 'chainhelix-grid/1', 'service': 'grid_plan',
                     'erc8004_token_id': 269224, 'task_input': normalized, 'request_nonce': nonce}
        expected_request = {'task_description': canonical_json(normalized), 'terms': {
            'deliverables': 'grid level plan with per-level sizes',
            'quality_standards': 'deterministic arithmetic, levels within the stated span; exact supplied inputs; no trading, custody or profit claim'}}
    from proofops.services import reviewed_calculators
    calculator_token = int(selected['token_id'])
    if calculator_token in reviewed_calculators.SERVICES:
        if arena_task is not None:
            raise ValueError('Calculator requires its own explicit inputs; Arena conversion is not authorized')
        if skill_id != reviewed_calculators.SERVICES[calculator_token][0]:
            raise ValueError('Calculator category mismatch')
        normalized = reviewed_calculators.inputs(calculator_token, task_input if task_input is not None else reviewed_calculators.sample(calculator_token))
        normalized['request_nonce'] = nonce
        task_spec = {'schema_version': 'chainhelix-calculator/1', 'service': skill_id,
                     'erc8004_token_id': calculator_token, 'task_input': normalized, 'request_nonce': nonce}
        expected_request = {'task_description': canonical_json(normalized), 'terms': {
            'deliverables': selected['description'],
            'quality_standards': 'Use the exact supplied inputs. Return complete readable calculation output and assumptions. One calculation only, no monitoring, transfers, trading or profit guarantee. Manual quality review required.'}}
    if quote_format == "bnbagent-sdk-v1":
        # The reviewed chain transaction always uses SafeHire's fixed router and
        # policy. Do not rely on unsigned SDK evaluator metadata.
        expected_request["terms"]["evaluation_required"] = True
        expected_request["terms"]["evaluator_type"] = "uma_oov3"
        expected_request["terms"]["quality_standards"] += (
            " Escrow evaluation uses SafeHire's reviewed BSC OptimisticPolicy "
            "0x9c01845705b3078aa2e8cff7520a6376fd766de5 through router "
            "0x51895229e12f9876011789b04f8698af06ccd6da; no alternate evaluator is authorized."
        )
    request = {
        "jsonrpc": "2.0",
        "id": nonce,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": nonce,
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "skill": "negotiate",
                            "service": skill_id,
                            "request": expected_request,
                            **expected_request,
                        },
                    }
                ],
            }
        },
    }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(route["endpoint"], json=request)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("live Agent returned an unexpected quote response")
    if payload.get("error") is not None:
        raise ValueError("live Agent rejected the quote request")

    envelope = find_negotiation_envelope(payload)
    if envelope is None:
        raise QuoteVerificationError(
            "live Agent did not return a complete signed ERC-8183 negotiation envelope"
        )
    service = find_named_value(payload.get("result"), "service")
    if service is not None and str(service) != skill_id:
        raise QuoteVerificationError("live Agent quote does not match the selected service")
    provider_raw = (
        find_named_value(payload.get("result"), "provider")
        or _provider_field(selected, catalog, "provider_address")
    )
    configured_provider = _provider_field(selected, catalog, "provider_address")
    if quote_format == "bnbagent-sdk-v1":
        if not isinstance(configured_provider, str) or len(configured_provider) != 42:
            raise QuoteVerificationError("SDK provider must have a reviewed registry wallet")
        if provider_raw is not None and str(provider_raw).lower() != configured_provider.lower():
            raise QuoteVerificationError("SDK quote provider differs from reviewed wallet")
        provider_raw = configured_provider
    if provider_raw is None:
        raise QuoteVerificationError("signed quote did not identify its provider account")

    payment_value = catalog.get("payment")
    payment = payment_value if isinstance(payment_value, dict) else {}
    expected_price = int(
        _provider_field(selected, catalog, "price_raw")
        or payment.get("price_raw")
        or DEFAULT_PRICE_RAW
    )
    expected_commerce = str(
        _provider_field(selected, catalog, "commerce_address") or DEFAULT_COMMERCE
    )
    expected_payment_token = str(
        _provider_field(selected, catalog, "payment_token")
        or payment.get("token_address")
        or DEFAULT_U_TOKEN
    )
    verified = await verify_negotiation_envelope(
        envelope=envelope,
        expected_request=expected_request,
        provider=str(provider_raw),
        expected_chain_id=56,
        expected_verifying_contract=expected_commerce,
        expected_payment_token=expected_payment_token,
        expected_price_raw=expected_price,
        rpc_url=rpc_url,
        rpc_call=rpc_call,
        quote_format=quote_format,
    )
    identity_verification: dict[str, Any] | None = None
    if quote_format == "bnbagent-sdk-v1":
        async def identity_rpc(method: str, params: list[Any]) -> Any:
            return await rpc_call(method, params) if rpc_call else await _default_rpc(rpc_url, method, params)
        from eth_abi.abi import decode, encode
        from eth_utils.crypto import keccak
        registry = "0x8004a169fb4a3325136eb29fa0ceb6d2e539a432"
        block = await identity_rpc("eth_getBlockByNumber", ["latest", False])
        if not isinstance(block, dict) or not _valid_tx_hash(block.get("hash")):
            raise QuoteVerificationError("SDK identity block is unavailable")
        calldata = "0x" + (keccak(text="getAgentWallet(uint256)")[:4] + encode(["uint256"], [int(selected["token_id"])])).hex()
        raw = await identity_rpc("eth_call", [{"to": registry, "data": calldata},
                                           {"blockHash": block["hash"], "requireCanonical": True}])
        decoded = decode(["address"], bytes.fromhex(str(raw)[2:]))[0]
        if encode(["address"], [decoded]).hex() != str(raw)[2:] or decoded.lower() != str(provider_raw).lower():
            raise QuoteVerificationError("SDK signer no longer matches the registered agent wallet")
        identity_verification = {"registry": registry, "block_hash": block["hash"],
                                 "agent_wallet": decoded, "signer_matches": True}
    response_object = envelope["response"]
    assert isinstance(response_object, dict)
    terms = response_object.get("terms")
    assert isinstance(terms, dict)

    return {
        "schema_version": "2.0",
        "evidence_mode": "live",
        "observed_at": datetime.now(UTC).isoformat(),
        "agent": {
            "name": selected.get("name"),
            "operator": route["operator"],
            "category": selected.get("category"),
            "skill_id": skill_id,
            "erc8004_token_id": selected.get("token_id"),
            "registration_url": selected.get("registry_url"),
            "agent_card_url": route["agent_card_url"],
            "a2a_endpoint": route["endpoint"],
            "requires_arena": selected.get("requires_arena") is True,
        },
        "task_spec": task_spec,
        "quote": {
            "accepted": True,
            "service": skill_id,
            "chain_id": verified.chain_id,
            "provider": verified.provider,
            "price": verified.price_raw,
            "price_display": f"{int(verified.price_raw) / 10**18:.2f} U",
            "payment_token": verified.payment_token,
            "verifying_contract": verified.verifying_contract,
            "estimated_completion_seconds": verified.estimated_completion_seconds,
            "quote_expires_at": verified.quote_expires_at,
            "deliverables": terms.get("deliverables"),
            "quality_standards": terms.get("quality_standards"),
            "success_criteria": terms.get("success_criteria") or [],
        },
        "quote_format": quote_format,
        "identity_verification": identity_verification,
        "quote_envelope": envelope,
        "quote_verification": verified.to_dict(),
        "next_action": "review_signed_quote_before_wallet_funding",
        "transaction_sent": False,
        "wallet_connected": False,
        "evidence_boundary": (
            "SafeHire verified the provider signature, request/response hashes, chain, commerce "
            "contract, exact token price and quote expiry. No wallet was connected and no token "
            "approval, job creation or payment occurred."
        ),
    }
