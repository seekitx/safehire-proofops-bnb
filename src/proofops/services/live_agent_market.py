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
        services = result.get("services") if isinstance(result, dict) else None
        if not isinstance(services, list) or result.get("can_sign") is not True:
            raise ValueError("A2A list response did not advertise signed hiring")
        for item in services:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                live_services[item["id"]] = item
        endpoint_reachable = True
    except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
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
