from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self

import httpx
import pytest

from proofops.services import live_agent_market


def _write_catalog(root: Path) -> None:
    target = root / "evidence" / "marketplace" / "live-agent-catalog.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "observed_at": "2026-08-30T00:00:00Z",
                "operator": "Independent Provider",
                "agents": [
                    {
                        "token_id": 101,
                        "skill_id": "grid_plan",
                        "name": "Grid Agent",
                        "category": "grid_trading",
                        "description": "Grid planning",
                    },
                    {
                        "token_id": 102,
                        "skill_id": "yield_plan",
                        "name": "Yield Agent",
                        "category": "yield_optimisation",
                        "description": "Yield planning",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


class FakeClient:
    def __init__(self, **_kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        request = httpx.Request("POST", url)
        data = json["params"]["message"]["parts"][0]["data"]
        if data["skill"] == "list":
            payload = {
                "result": {
                    "can_sign": True,
                    "services": [
                        {"id": "grid_plan", "price_display": "0.10 $U"},
                        {"id": "yield_plan", "price_display": "0.10 $U"},
                    ],
                }
            }
        else:
            payload = {
                "result": {
                    "accepted": True,
                    "service": data["service"],
                    "chain_id": 56,
                    "provider": "0x2222222222222222222222222222222222222222",
                    "price": "100000000000000000",
                    "price_display": "0.10 $U",
                    "verifying_contract": "0xEa4DAa3100A767e86FDed867729ae7446476EBA6",
                    "payment_token": "0xcE24439F2D9C6a2289F741120FE202248B666666",
                    "estimated_completion_seconds": 120,
                }
            }
        return httpx.Response(200, json=payload, request=request)

    async def get(self, url: str) -> httpx.Response:
        request = httpx.Request("GET", url)
        token_id = url.rsplit("/", 1)[-1]
        return httpx.Response(
            200,
            json={
                "token_id": token_id,
                "is_active": True,
                "is_verified": True,
                "is_endpoint_verified": False,
                "total_score": 4.5,
                "quality_score": 4,
                "health_score": 2,
                "metadata_completeness_score": 5,
                "total_feedbacks": 1,
                "total_validations": 2,
                "successful_validations": 1,
                "supported_protocols": ["A2A"],
                "health_status": {
                    "overall_status": "unhealthy",
                    "services": {"a2a": {"status": "unhealthy", "latency_ms": 200}},
                },
            },
            request=request,
        )


@pytest.mark.anyio
async def test_live_market_combines_current_probe_and_index_signals(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_catalog(tmp_path)
    monkeypatch.setattr(live_agent_market.httpx, "AsyncClient", FakeClient)

    result = await live_agent_market.live_agent_market(tmp_path)

    assert result["endpoint_reachable"] is True
    assert result["operator_count"] == 1
    assert len(result["agents"]) == 2
    assert all(item["currently_callable"] for item in result["agents"])
    assert result["agents"][0]["market_signals"]["total_feedbacks"] == 1
    assert "cached health" in result["agents"][0]["signal_disagreement"]
    assert result["agents"][0]["safehire_paid_deliveries"] == 0


@pytest.mark.anyio
async def test_live_quote_is_read_only_and_allowlisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_catalog(tmp_path)
    monkeypatch.setattr(live_agent_market.httpx, "AsyncClient", FakeClient)

    result = await live_agent_market.request_live_agent_quote(
        tmp_path, skill_id="grid_plan"
    )

    assert result["quote"]["price_display"] == "0.10 $U"
    assert result["transaction_sent"] is False
    assert result["wallet_connected"] is False

    with pytest.raises(ValueError, match="reviewed live BSC catalog"):
        await live_agent_market.request_live_agent_quote(tmp_path, skill_id="unknown")
