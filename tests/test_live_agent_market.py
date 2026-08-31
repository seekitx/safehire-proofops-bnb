from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Self

import httpx
import pytest
from eth_account import Account
from eth_account.messages import encode_defunct

from proofops.integrations.erc8183_quote import (
    build_description_content,
    canonical_keccak,
    response_hash_content,
)
from proofops.services import live_agent_market

ACCOUNT = Account.create()
COMMERCE = live_agent_market.DEFAULT_COMMERCE
TOKEN = live_agent_market.DEFAULT_U_TOKEN
PRICE = live_agent_market.DEFAULT_PRICE_RAW


def _write_catalog(root: Path) -> None:
    target = root / "evidence" / "marketplace" / "live-agent-catalog.json"
    target.parent.mkdir(parents=True)
    target.write_text(
        json.dumps(
            {
                "evidence_mode": "live",
                "observed_at": "2026-08-30T00:00:00Z",
                "operator": "Independent Provider",
                "a2a_endpoint": "https://provider.example/a2a",
                "agent_card_url": "https://provider.example/.well-known/agent-card.json",
                "payment": {"price_raw": str(PRICE)},
                "agents": [
                    {
                        "token_id": 101,
                        "skill_id": "grid_plan",
                        "name": "Grid Agent",
                        "category": "grid_trading",
                        "description": "Grid planning",
                        "required_inputs": {"token": "token address"},
                    },
                    {
                        "token_id": 102,
                        "skill_id": "yield_plan",
                        "name": "Yield Agent",
                        "category": "yield_optimisation",
                        "description": "Yield planning",
                        "required_inputs": {"amountUsd": "position size"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )


def _signed_envelope(request: dict[str, Any]) -> dict[str, Any]:
    now = 1_800_000_000
    response = {
        "accepted": True,
        "terms": {
            **request["terms"],
            "price": str(PRICE),
            "currency": TOKEN,
        },
        "estimated_completion_seconds": 120,
        "quote_expires_at": now + 600,
        "negotiated_at": now,
    }
    envelope: dict[str, Any] = {
        "request": request,
        "request_hash": canonical_keccak(request),
        "response": response,
        "response_hash": canonical_keccak(response_hash_content(response)),
        "chain_id": 56,
        "verifying_contract": COMMERCE,
    }
    envelope["negotiation_hash"] = canonical_keccak(build_description_content(envelope))
    signature = Account.sign_message(
        encode_defunct(text=envelope["negotiation_hash"]), ACCOUNT.key
    ).signature.hex()
    envelope["provider_sig"] = signature if signature.startswith("0x") else f"0x{signature}"
    return envelope


async def fake_rpc(method: str, _params: list[Any]) -> Any:
    if method == "eth_chainId":
        return "0x38"
    if method == "eth_getBlockByNumber":
        return {"timestamp": hex(1_800_000_100)}
    if method == "eth_getCode":
        return "0x"
    raise AssertionError(method)


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
                        {"id": "grid_plan", "price_display": "0.10 U"},
                        {"id": "yield_plan", "price_display": "0.10 U"},
                    ],
                }
            }
        else:
            payload = {
                "result": {
                    "accepted": True,
                    "service": data["service"],
                    "provider": ACCOUNT.address,
                    "negotiation": _signed_envelope(data["request"]),
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
async def test_live_market_combines_current_probe_index_and_paid_history(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_catalog(tmp_path)
    paid = tmp_path / "evidence" / "marketplace" / "paid-deliveries"
    paid.mkdir()
    (paid / "job-1.json").write_text(
        json.dumps(
            {
                "evidence_mode": "live",
                "verification_status": "mainnet_verified",
                "chain_id": 56,
                "external_provider": True,
                "paid": True,
                "erc8004_token_id": 101,
                "settlement_tx_hash": "0x" + "12" * 32,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(live_agent_market.httpx, "AsyncClient", FakeClient)

    result = await live_agent_market.live_agent_market(tmp_path)

    assert result["endpoint_reachable"] is True
    assert result["endpoint_count"] == 1
    assert result["operator_count"] == 1
    assert len(result["agents"]) == 2
    assert all(item["currently_callable"] for item in result["agents"])
    assert result["agents"][0]["market_signals"]["total_feedbacks"] == 1
    assert "cached health" in result["agents"][0]["signal_disagreement"]
    assert result["agents"][0]["safehire_paid_deliveries"] == 1


@pytest.mark.anyio
async def test_live_quote_verifies_signature_and_binds_reviewed_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_catalog(tmp_path)
    monkeypatch.setattr(live_agent_market.httpx, "AsyncClient", FakeClient)

    result = await live_agent_market.request_live_agent_quote(
        tmp_path,
        skill_id="grid_plan",
        agent_token_id=101,
        task_input={"token": "0x3333333333333333333333333333333333333333"},
        request_nonce="safehire-test-request-0003",
        rpc_call=fake_rpc,
    )

    assert result["quote"]["price_display"] == "0.10 U"
    assert result["quote_verification"]["signature_method"] == "eip191"
    assert result["task_spec"]["erc8004_token_id"] == 101
    assert result["transaction_sent"] is False
    assert result["wallet_connected"] is False

    with pytest.raises(ValueError, match="reviewed live BSC catalog"):
        await live_agent_market.request_live_agent_quote(
            tmp_path, skill_id="unknown", rpc_call=fake_rpc
        )
