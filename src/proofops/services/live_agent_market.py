from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

A2A_CARD_URL = "https://agent.brainonbnb.com/.well-known/agent-card.json"
A2A_ENDPOINT = "https://agent.brainonbnb.com/a2a"


def _load_catalog(project_root: Path) -> dict[str, Any]:
    path = project_root / "evidence" / "marketplace" / "live-agent-catalog.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("live BSC agent catalog is missing or malformed") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("agents"), list):
        raise TypeError("live BSC agent catalog has an unexpected schema")
    return payload


async def live_agent_market(project_root: Path) -> dict[str, Any]:
    """Combine a reviewable ERC-8004 snapshot with current A2A liveness.

    The saved snapshot proves which four registrations were selected. The live
    request only calls the provider's free `list` skill; it never negotiates,
    signs, funds, or starts an ERC-8183 job.
    """

    catalog = _load_catalog(project_root)
    observed_at = datetime.now(UTC).isoformat()
    live_services: dict[str, dict[str, Any]] = {}
    endpoint_reachable = False
    liveness_error = None
    try:
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "messageId": "safehire-public-discovery",
                    "parts": [{"kind": "data", "data": {"skill": "list"}}],
                }
            },
        }
        async with httpx.AsyncClient(timeout=12) as client:
            response = await client.post(A2A_ENDPOINT, json=request)
            response.raise_for_status()
            payload = response.json()
        result = payload.get("result") if isinstance(payload, dict) else None
        if not isinstance(result, dict):
            raise TypeError("A2A list response returned no result object")
        services = result.get("services")
        if not isinstance(services, list) or result.get("can_sign") is not True:
            raise ValueError("A2A list response did not advertise signed hiring")
        for item in services:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                live_services[item["id"]] = item
        endpoint_reachable = True
    except (httpx.HTTPError, TypeError, ValueError, json.JSONDecodeError) as exc:
        liveness_error = type(exc).__name__

    agents: list[dict[str, Any]] = []
    for item in catalog["agents"]:
        if not isinstance(item, dict):
            continue
        skill_id = str(item.get("skill_id", ""))
        current = live_services.get(skill_id)
        agents.append(
            {
                **item,
                "current_capability": current,
                "currently_callable": endpoint_reachable and current is not None,
            }
        )
    return {
        "source": "erc8004_snapshot_plus_live_a2a_list",
        "observed_at": observed_at,
        "registration_snapshot_observed_at": catalog.get("observed_at"),
        "endpoint": A2A_ENDPOINT,
        "agent_card_url": A2A_CARD_URL,
        "endpoint_reachable": endpoint_reachable,
        "liveness_error": liveness_error,
        "agents": agents,
        "trust_boundary": (
            "Registrations and endpoint discovery are verified. No paid job was started; "
            "execution history and output quality remain unverified until a real hire is captured."
        ),
    }


async def request_live_agent_quote(project_root: Path, *, skill_id: str) -> dict[str, Any]:
    """Request an allowlisted commercial quote without funding or signing.

    SafeHire builds the task description from its reviewed catalog rather than
    relaying arbitrary visitor prose. The upstream Agent may return a provider,
    price and escrow instructions, but this endpoint never calls a wallet and
    never creates, approves or funds an ERC-8183 job.
    """

    catalog = _load_catalog(project_root)
    selected = next(
        (
            item
            for item in catalog["agents"]
            if isinstance(item, dict) and item.get("skill_id") == skill_id
        ),
        None,
    )
    if selected is None:
        raise ValueError("skill_id is not in the reviewed live BSC catalog")

    category = str(selected.get("category", "unknown"))
    description = str(selected.get("description", "")).strip()
    request = {
        "jsonrpc": "2.0",
        "id": f"safehire-quote-{skill_id}",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "messageId": f"safehire-quote-{skill_id}",
                "parts": [
                    {
                        "kind": "data",
                        "data": {
                            "skill": "negotiate",
                            "service": skill_id,
                            "task_description": (
                                f"Prepare a bounded {category} analysis for review in "
                                "SafeHire. Do not trade, approve tokens or move funds."
                            ),
                            "terms": {
                                "deliverables": description,
                                "quality_standards": (
                                    "Use current BNB Chain evidence, name sources and "
                                    "timestamps, disclose uncertainty, and never promise profit."
                                ),
                            },
                        },
                    }
                ],
            }
        },
    }

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(A2A_ENDPOINT, json=request)
        response.raise_for_status()
        payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError("live Agent returned an unexpected quote response")
    if payload.get("error") is not None:
        raise ValueError("live Agent rejected the quote request")
    quote = payload.get("result")
    if not isinstance(quote, dict) or quote.get("accepted") is not True:
        raise ValueError("live Agent did not return an accepted quote")
    if str(quote.get("service", "")) != skill_id:
        raise ValueError("live Agent quote does not match the selected service")

    return {
        "schema_version": "1.0",
        "evidence_mode": "live",
        "observed_at": datetime.now(UTC).isoformat(),
        "agent": {
            "name": selected.get("name"),
            "category": category,
            "skill_id": skill_id,
            "erc8004_token_id": selected.get("token_id"),
            "registration_url": selected.get("registry_url"),
        },
        "quote": quote,
        "next_action": "review_mainnet_quote_before_wallet_funding",
        "transaction_sent": False,
        "evidence_boundary": (
            "A live external Agent accepted the commercial request and returned its current "
            "provider, price and ERC-8183 funding instructions. SafeHire did not connect a "
            "wallet, sign, approve a token, create a job or move funds."
        ),
    }
