from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Self

import pytest
from eth_abi.abi import encode

from proofops.services import live_erc8183

BUYER = "0x1111111111111111111111111111111111111111"
PROVIDER = "0x2222222222222222222222222222222222222222"
TOKEN_A = "0x3333333333333333333333333333333333333333"
TOKEN_B = "0x4444444444444444444444444444444444444444"


def _quote_payload() -> dict[str, Any]:
    return {
        "observed_at": "2026-08-31T00:00:00Z",
        "agent": {"name": "External Agent", "erc8004_token_id": 42},
        "quote": {
            "chain_id": 56,
            "provider": PROVIDER,
            "verifying_contract": live_erc8183.COMMERCE,
            "payment_token": live_erc8183.U_TOKEN,
            "price": str(live_erc8183.PRICE_RAW),
            "price_display": "0.10 $U",
        },
    }


def _encoded_job(
    *,
    status: int,
    description: dict[str, Any] | str,
    expires_at: int | None = None,
) -> str:
    description_text = (
        json.dumps(description, separators=(",", ":"))
        if isinstance(description, dict)
        else description
    )
    fields = (
        77,
        BUYER,
        PROVIDER,
        live_erc8183.ROUTER,
        description_text,
        live_erc8183.PRICE_RAW,
        expires_at or int(time.time()) + 3600,
        status,
        live_erc8183.U_TOKEN,
        int(time.time()) - 100,
        b"\x01" * 32,
    )
    return "0x" + encode(
        ["(uint256,address,address,address,string,uint256,uint256,uint8,address,uint256,bytes32)"],
        [fields],
    ).hex()


@pytest.mark.parametrize(
    ("skill_id", "raw", "expected_key"),
    [
        (
            "grid_plan",
            {"token": TOKEN_A, "capitalUsd": 1000, "levels": 9, "bandPct": 5},
            "levels",
        ),
        (
            "yield_plan",
            {"amountUsd": 5000, "from": "Venus USDT", "currentApyPct": 3.2},
            "from",
        ),
        ("health_factor", {"address": BUYER}, "address"),
        (
            "rebalance_plan",
            {
                "holdings": [
                    {"token": TOKEN_A, "usd": 600},
                    {"token": TOKEN_B, "usd": 400},
                ],
                "targets": {TOKEN_A: 50, TOKEN_B: 50},
            },
            "targets",
        ),
    ],
)
def test_validate_live_task_inputs(
    skill_id: str, raw: dict[str, Any], expected_key: str
) -> None:
    result = live_erc8183.validate_task_input(skill_id, raw)

    assert expected_key in result


@pytest.mark.parametrize(
    ("skill_id", "raw", "message"),
    [
        ("missing", {}, "approved live-market"),
        ("grid_plan", {"token": TOKEN_A, "levels": 2.5}, "whole number"),
        ("yield_plan", {"from": ""}, "current Venus market"),
        (
            "rebalance_plan",
            {"holdings": [{"token": TOKEN_A, "usd": 1}]},
            "between 2 and 20",
        ),
        (
            "health_factor",
            {"address": BUYER, "secret": "no"},
            "accepts only address",
        ),
    ],
)
def test_validate_live_task_inputs_fail_closed(
    skill_id: str, raw: dict[str, Any], message: str
) -> None:
    with pytest.raises((TypeError, ValueError), match=message):
        live_erc8183.validate_task_input(skill_id, raw)


@pytest.mark.anyio
async def test_prepare_live_hire_returns_unsigned_exact_value_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_quote(_root: Path, *, skill_id: str) -> dict[str, Any]:
        assert skill_id == "grid_plan"
        return _quote_payload()

    monkeypatch.setattr(live_erc8183, "request_live_agent_quote", fake_quote)

    plan = await live_erc8183.prepare_live_hire(
        Path("."),
        buyer=BUYER,
        skill_id="grid_plan",
        task_input={"token": TOKEN_A, "capitalUsd": 1000, "levels": 9},
    )

    assert plan["chain_id"] == 56
    assert plan["quote"]["price"] == str(live_erc8183.PRICE_RAW)
    assert plan["transaction"]["to"] == live_erc8183.COMMERCE
    assert plan["transaction"]["data"].startswith("0x")
    assert plan["safety"]["manual_wallet_confirmation_per_write"] is True
    assert plan["safety"]["unlimited_approval"] is False


@pytest.mark.anyio
async def test_live_job_status_decodes_funded_and_submitted_jobs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = {
        "service": "grid_plan",
        "provider": PROVIDER,
        "price_raw": str(live_erc8183.PRICE_RAW),
        "task_input": {"token": TOKEN_A},
    }

    async def funded_rpc(_method: str, _params: list[Any]) -> str:
        return _encoded_job(status=1, description=description)

    monkeypatch.setattr(live_erc8183, "_rpc", funded_rpc)
    funded = await live_erc8183.live_job_status(job_id=77)
    assert funded["status"] == "FUNDED"
    assert funded["budget_u"] == "0.1"
    assert funded["can_settle"] is False

    async def submitted_rpc(_method: str, _params: list[Any]) -> str:
        return _encoded_job(status=2, description=description)

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list[dict[str, Any]]:
            return [
                {
                    "id": 1,
                    "result": "0x" + encode(["uint8", "bytes32"], [1, b"\x02" * 32]).hex(),
                },
                {"id": 2, "result": "0x" + encode(["uint64"], [100]).hex()},
                {"id": 3, "result": "0x" + encode(["uint64"], [15]).hex()},
                {"id": 4, "result": "0x" + encode(["bool"], [False]).hex()},
            ]

    class FakeClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, *_args: Any, **_kwargs: Any) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(live_erc8183, "_rpc", submitted_rpc)
    monkeypatch.setattr(live_erc8183.httpx, "AsyncClient", FakeClient)
    submitted = await live_erc8183.live_job_status(job_id=77)

    assert submitted["status"] == "SUBMITTED"
    assert submitted["policy_verdict"] == "APPROVE"
    assert submitted["can_settle"] is True


@pytest.mark.anyio
async def test_live_followup_notify_settle_and_refund_plans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    description = {
        "service": "grid_plan",
        "provider": PROVIDER,
        "price_raw": str(live_erc8183.PRICE_RAW),
        "task_input": {"token": TOKEN_A},
    }
    base_status = {
        "client": BUYER,
        "provider": PROVIDER,
        "description": description,
        "status": "OPEN",
        "budget_raw": str(live_erc8183.PRICE_RAW),
        "completed": False,
        "can_settle": False,
        "can_refund": False,
    }

    async def open_status(*, job_id: int) -> dict[str, Any]:
        assert job_id == 77
        return dict(base_status)

    monkeypatch.setattr(live_erc8183, "live_job_status", open_status)
    followup = await live_erc8183.live_followup_plan(
        buyer=BUYER, skill_id="grid_plan", job_id=77
    )
    assert [item["step"] for item in followup["transactions"]] == [
        "register_job",
        "set_budget",
        "approve_u",
        "fund_job",
    ]
    assert followup["transactions"][2]["to"] == live_erc8183.U_TOKEN

    class NotifyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, Any]:
            return {"result": {"accepted": True}}

    class NotifyClient:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        async def __aenter__(self) -> Self:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(self, _url: str, *, json: dict[str, Any]) -> NotifyResponse:
            data = json["params"]["message"]["parts"][0]["data"]
            assert data["skill"] == "notify_funded"
            assert data["job_id"] == 77
            return NotifyResponse()

    async def funded_status(*, job_id: int) -> dict[str, Any]:
        return {**base_status, "status": "FUNDED"}

    monkeypatch.setattr(live_erc8183, "live_job_status", funded_status)
    monkeypatch.setattr(live_erc8183.httpx, "AsyncClient", NotifyClient)
    notification = await live_erc8183.notify_live_agent(
        job_id=77, skill_id="grid_plan"
    )
    assert notification["agent_response"] == {"accepted": True}
    assert notification["transaction_sent"] is False

    async def submitted_status(*, job_id: int) -> dict[str, Any]:
        return {
            **base_status,
            "status": "SUBMITTED",
            "can_settle": True,
            "policy_verdict": "APPROVE",
        }

    monkeypatch.setattr(live_erc8183, "live_job_status", submitted_status)
    settlement = await live_erc8183.live_settle_plan(job_id=77)
    assert settlement["transaction"]["to"] == live_erc8183.ROUTER

    async def expired_status(*, job_id: int) -> dict[str, Any]:
        return {**base_status, "status": "FUNDED", "can_refund": True}

    monkeypatch.setattr(live_erc8183, "live_job_status", expired_status)
    refund = await live_erc8183.live_refund_plan(job_id=77)
    assert refund["transaction"]["to"] == live_erc8183.COMMERCE
