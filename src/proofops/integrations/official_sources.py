from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from proofops.domain.errors import AdapterUnavailableError

SCAN8004_BASE = "https://api.8004scan.io/api/v1"
VENUS_BASE = "https://api.venus.io"
LISTA_BASE = "https://api.lista.org/api/moolah"
PANCAKE_GRAPH_GATEWAY = "https://gateway.thegraph.com/api"


class OfficialSourceClient:
    """Read-only clients for sponsor/protocol discovery data.

    API responses are treated as untrusted input. These methods validate only the
    fields SafeHire needs and never silently replace a failed live call with a fixture.
    """

    def __init__(
        self,
        *,
        timeout_seconds: float = 10,
        scan8004_api_key: str = "",
        the_graph_api_key: str = "",
        pancake_v3_subgraph_id: str = "",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._scan8004_api_key = scan8004_api_key
        self._the_graph_api_key = the_graph_api_key
        self._pancake_v3_subgraph_id = pancake_v3_subgraph_id
        self._transport = transport

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.get(url, params=params, headers=headers)
                response.raise_for_status()
                return response.json()
        except Exception as exc:
            safe = re.sub(r"https?://\S+", "<official-source>", str(exc))
            raise AdapterUnavailableError(f"official source unavailable: {safe}") from exc

    async def scan8004_agents(self, *, chain_id: int = 97, limit: int = 20) -> dict[str, Any]:
        if chain_id not in {56, 97}:
            raise ValueError("chain_id must be 56 or 97")
        if not 1 <= limit <= 100:
            raise ValueError("limit must be in [1, 100]")
        headers = {"X-API-Key": self._scan8004_api_key} if self._scan8004_api_key else {}
        payload = await self._get(
            f"{SCAN8004_BASE}/agents",
            params={"chain_id": chain_id, "limit": limit, "offset": 0},
            headers=headers,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            raise AdapterUnavailableError("8004scan returned an unexpected schema")
        items = [item for item in payload["items"] if isinstance(item, dict)]
        return {
            "source": "8004scan_official_api",
            "chain_id": chain_id,
            "items": items,
            "total": int(payload.get("total", len(items))),
            "observed_at": datetime.now(UTC).isoformat(),
            "trust_boundary": "Index data; identity owner and URI still require RPC verification.",
        }

    async def scan8004_agent(self, *, chain_id: int, token_id: int) -> dict[str, Any]:
        if chain_id not in {56, 97}:
            raise ValueError("chain_id must be 56 or 97")
        if token_id <= 0:
            raise ValueError("token_id must be positive")
        headers = {"X-API-Key": self._scan8004_api_key} if self._scan8004_api_key else {}
        payload = await self._get(
            f"{SCAN8004_BASE}/agents/{chain_id}/{token_id}",
            headers=headers,
        )
        if not isinstance(payload, dict) or str(payload.get("token_id", "")) != str(token_id):
            raise AdapterUnavailableError("8004scan returned an unexpected Agent schema")
        return payload

    async def validate_agent_intake(self, *, chain_id: int, token_id: int) -> dict[str, Any]:
        """Build a read-only listing dossier from the official ERC-8004 index.

        The endpoint intentionally does not call an arbitrary URL supplied by a visitor.
        Endpoint health remains the indexer's claim until a controlled SafeHire probe is added.
        """

        payload = await self.scan8004_agent(chain_id=chain_id, token_id=token_id)
        protocols = [str(item).upper() for item in payload.get("supported_protocols", [])]
        raw_categories = payload.get("categories") or payload.get("tags") or []
        category_text = " ".join(str(item).lower() for item in raw_categories)
        name_and_description = (
            f"{payload.get('name', '')} {payload.get('description', '')}".lower()
        )
        searchable = f"{category_text} {name_and_description}"
        category_aliases = {
            "rebalancing": ("rebalance", "rebalancing", "liquidity range", "lp range"),
            "grid_trading": ("grid", "grid-trading", "grid trading"),
            "yield_optimisation": (
                "yield",
                "yield-optimization",
                "yield optimisation",
                "yield optimization",
            ),
            "health_factor_monitoring": (
                "health factor",
                "health-factor",
                "liquidation",
            ),
        }
        matched_categories = [
            category
            for category, aliases in category_aliases.items()
            if any(alias in searchable for alias in aliases)
        ]
        a2a_endpoint = payload.get("a2a_endpoint")
        checks = [
            {
                "id": "active_registration",
                "passed": payload.get("is_active") is True,
                "detail": "ERC-8004 record is active",
            },
            {
                "id": "a2a_metadata",
                "passed": "A2A" in protocols and isinstance(a2a_endpoint, str),
                "detail": "A2A protocol and endpoint are present in indexed metadata",
            },
            {
                "id": "official_category",
                "passed": bool(matched_categories),
                "detail": "At least one official marketplace category can be identified",
            },
            {
                "id": "endpoint_index_verification",
                "passed": payload.get("is_endpoint_verified") is True,
                "detail": "8004scan currently marks the endpoint as verified",
            },
            {
                "id": "reputation_signal",
                "passed": int(payload.get("total_feedbacks") or 0) > 0,
                "detail": "At least one indexed feedback record exists",
            },
        ]
        blocking_ids = {"active_registration", "a2a_metadata", "official_category"}
        eligible = all(item["passed"] for item in checks if item["id"] in blocking_ids)
        return {
            "schema_version": "1.0",
            "source": "8004scan_official_api",
            "observed_at": datetime.now(UTC).isoformat(),
            "chain_id": chain_id,
            "token_id": str(token_id),
            "agent": {
                "name": payload.get("name"),
                "description": payload.get("description"),
                "owner_address": payload.get("owner_address"),
                "agent_wallet": payload.get("agent_wallet"),
                "a2a_endpoint": a2a_endpoint,
                "supported_protocols": protocols,
                "matched_categories": matched_categories,
                "is_active": payload.get("is_active"),
                "is_endpoint_verified": payload.get("is_endpoint_verified"),
            },
            "signals": {
                "total_score": payload.get("total_score"),
                "quality_score": payload.get("quality_score"),
                "health_score": payload.get("health_score"),
                "metadata_completeness_score": payload.get("metadata_completeness_score"),
                "total_feedbacks": int(payload.get("total_feedbacks") or 0),
                "total_validations": int(payload.get("total_validations") or 0),
                "successful_validations": int(payload.get("successful_validations") or 0),
                "endpoint_last_checked_at": payload.get("endpoint_last_checked_at"),
                "health_status": payload.get("health_status"),
            },
            "checks": checks,
            "eligible_for_review": eligible,
            "listing_created": False,
            "next_action": (
                "submit evidence and a live commercial quote for curator review"
                if eligible
                else "fix the failed blocking checks before curator review"
            ),
            "trust_boundary": (
                "This is a read-only intake preview, not an approved listing. SafeHire did not "
                "call the indexed endpoint, accept funds or create an ERC-8004 record."
            ),
        }

    async def venus_pools(self, *, chain_id: int = 56) -> dict[str, Any]:
        if chain_id not in {56, 97}:
            raise ValueError("chain_id must be 56 or 97")
        payload = await self._get(f"{VENUS_BASE}/pools", params={"chainId": chain_id})
        if isinstance(payload, dict):
            pools = payload.get("pools") or payload.get("result") or payload.get("data")
        else:
            pools = payload
        if not isinstance(pools, list):
            raise AdapterUnavailableError("Venus returned an unexpected pools schema")
        return {
            "source": "venus_official_api",
            "chain_id": chain_id,
            "pools": [item for item in pools if isinstance(item, dict)],
            "observed_at": datetime.now(UTC).isoformat(),
            "trust_boundary": "Discovery data; account liquidity decisions require Comptroller RPC reads.",
        }

    async def lista_vaults(self, *, limit: int = 20) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be in [1, 100]")
        payload = await self._get(
            f"{LISTA_BASE}/vault/list",
            params={
                "sort": "depositsUsd",
                "order": "desc",
                "zone": 0,
                "chain": "bsc",
            },
        )
        if isinstance(payload, dict):
            vaults = payload.get("data") or payload.get("list") or payload.get("vaults")
            if isinstance(vaults, dict):
                vaults = vaults.get("list") or vaults.get("items")
        else:
            vaults = payload
        if not isinstance(vaults, list):
            raise AdapterUnavailableError("Lista returned an unexpected vault schema")
        return {
            "source": "lista_official_api",
            "chain_id": 56,
            "vaults": [item for item in vaults[:limit] if isinstance(item, dict)],
            "observed_at": datetime.now(UTC).isoformat(),
            "trust_boundary": "Official MCP backing API; critical decisions require SDK or RPC verification.",
        }

    async def pancake_position(self, position_id: str) -> dict[str, Any]:
        if not position_id.strip():
            raise ValueError("position_id is required")
        if not self._the_graph_api_key:
            raise AdapterUnavailableError(
                "THE_GRAPH_API_KEY is required for the PancakeSwap production gateway"
            )
        if not self._pancake_v3_subgraph_id:
            raise AdapterUnavailableError("PANCAKE_V3_SUBGRAPH_ID is not configured")
        query = """
        query Position($id: ID!) {
          position(id: $id) {
            id owner liquidity depositedToken0 depositedToken1
            withdrawnToken0 withdrawnToken1 collectedFeesToken0 collectedFeesToken1
            tickLower { tickIdx } tickUpper { tickIdx }
            pool {
              id tick sqrtPrice liquidity feeTier
              token0 { id symbol decimals }
              token1 { id symbol decimals }
            }
          }
          _meta { block { number hash } }
        }
        """
        url = (
            f"{PANCAKE_GRAPH_GATEWAY}/{self._the_graph_api_key}/subgraphs/id/"
            f"{self._pancake_v3_subgraph_id}"
        )
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                response = await client.post(
                    url, json={"query": query, "variables": {"id": position_id}}
                )
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise AdapterUnavailableError(
                f"PancakeSwap subgraph unavailable: {type(exc).__name__}"
            ) from exc
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("_meta"), dict):
            raise AdapterUnavailableError("PancakeSwap subgraph returned an unexpected schema")
        return {
            "source": "pancakeswap_official_v3_subgraph",
            "chain_id": 56,
            "position": data.get("position"),
            "block": data["_meta"].get("block"),
            "observed_at": datetime.now(UTC).isoformat(),
            "trust_boundary": "Discovery data; decision-critical pool state requires same-block BSC RPC verification.",
        }

    async def readiness(self) -> dict[str, Any]:
        """Probe independent sources without hiding partial failure."""

        probes: dict[str, Any] = {}
        for name, call in (
            ("8004scan", self.scan8004_agents(limit=1)),
            ("venus", self.venus_pools()),
            ("lista", self.lista_vaults(limit=1)),
        ):
            try:
                result = await call
                probes[name] = {
                    "available": True,
                    "source": result["source"],
                    "observed_at": result["observed_at"],
                }
            # A readiness probe must report each independent upstream failure.
            except Exception as exc:  # noqa: BLE001
                probes[name] = {
                    "available": False,
                    "error": type(exc).__name__,
                }
        probes["pancakeswap"] = {
            "available": bool(self._the_graph_api_key),
            "configured": bool(self._the_graph_api_key),
            "reason": (
                "Position query is ready"
                if self._the_graph_api_key
                else "THE_GRAPH_API_KEY is not configured"
            ),
        }
        return {"sources": probes, "fixture_fallback": False}
