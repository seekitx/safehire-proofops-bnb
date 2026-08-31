from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Self

import pytest
from eth_abi.abi import encode
from eth_utils.crypto import keccak

from proofops.integrations.erc8183_quote import canonical_json
from proofops.services import live_erc8183

BUYER = "0x1111111111111111111111111111111111111111"
PROVIDER = "0x2222222222222222222222222222222222222222"
TOKEN_A = "0x3333333333333333333333333333333333333333"
TOKEN_B = "0x4444444444444444444444444444444444444444"


def _task_spec() -> dict[str, Any]:
    return {
        "schema_version": "safehire-external-hire-v2",
        "service": "grid_plan",
        "erc8004_token_id": 42,
        "request_nonce": "safehire-test-request-0004",
        "task_input": {"token": TOKEN_A},
    }


def _description() -> dict[str, Any]:
    return {
        "version": 1,
        "negotiated_at": int(time.time()) - 100,
        "quote_expires_at": int(time.time()) + 600,
        "task": canonical_json(_task_spec()),
        "terms": {
            "deliverables": "Grid report",
            "quality_standards": "Cite sources and risks",
            "success_criteria": ["Cite current evidence"],
        },
        "price": str(live_erc8183.PRICE_RAW),
        "currency": live_erc8183.U_TOKEN,
        "chain_id": 56,
        "verifying_contract": live_erc8183.COMMERCE,
        "negotiation_hash": "0x" + "01" * 32,
        "provider_sig": "0x" + "02" * 65,
    }


def _encoded_job(
    *,
    status: int,
    expires_at: int | None = None,
    budget: int | None = None,
    deliverable_hash: bytes | None = None,
) -> str:
    fields = (
        77,
        BUYER,
        PROVIDER,
        live_erc8183.ROUTER,
        json.dumps(_description(), separators=(",", ":")),
        live_erc8183.PRICE_RAW if budget is None else budget,
        expires_at or int(time.time()) + 3600,
        status,
        live_erc8183.U_TOKEN,
        int(time.time()) - 100,
        deliverable_hash or b"\x01" * 32,
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
async def test_prepare_live_hire_uses_signed_description_and_dynamic_timeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_quote(
        _root: Path, **_kwargs: Any
    ) -> dict[str, Any]:
        return {
            "agent": {"name": "External Agent", "erc8004_token_id": 42},
            "quote": {"provider": PROVIDER, "price": str(live_erc8183.PRICE_RAW)},
            "quote_verification": {
                "provider": PROVIDER,
                "job_description": canonical_json(_description()),
                "estimated_completion_seconds": 240,
                "quote_expires_at": int(time.time()) + 600,
                "signature_method": "eip191",
            },
        }

    async def fake_window() -> int:
        return 900

    monkeypatch.setattr(live_erc8183, "request_live_agent_quote", fake_quote)
    monkeypatch.setattr(live_erc8183, "_policy_dispute_window", fake_window)

    plan = await live_erc8183.prepare_live_hire(
        Path("."),
        buyer=BUYER,
        skill_id="grid_plan",
        agent_token_id=42,
        task_input={"token": TOKEN_A, "capitalUsd": 1000, "levels": 9},
    )

    assert plan["chain_id"] == 56
    assert plan["transaction"]["to"] == live_erc8183.COMMERCE
    assert plan["transaction"]["data"].startswith("0x")
    assert plan["timeline"]["dispute_window_seconds"] == 900
    assert plan["timeline"]["job_expires_at"] > plan["timeline"]["quote_expires_at"]
    assert plan["safety"]["signed_task_bound"] is True
    assert plan["safety"]["unlimited_approval"] is False


@pytest.mark.anyio
async def test_live_job_status_decodes_and_closes_settlement_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_verify(_description: Any, *, provider: str) -> dict[str, Any]:
        return {"valid": True, "provider": provider, "signature_method": "eip191"}

    async def funded_rpc(_method: str, _params: list[Any]) -> str:
        return _encoded_job(status=1)

    monkeypatch.setattr(live_erc8183, "_verify_anchored_description", fake_verify)
    monkeypatch.setattr(live_erc8183, "_rpc", funded_rpc)
    funded = await live_erc8183.live_job_status(job_id=77)
    assert funded["status"] == "FUNDED"
    assert funded["budget_u"] == "0.1"
    assert funded["task_spec"]["erc8004_token_id"] == 42

    async def submitted_rpc(_method: str, _params: list[Any]) -> str:
        return _encoded_job(status=2)

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
    assert submitted["review_window_closed"] is True
    assert submitted["can_settle"] is True
    assert submitted["can_dispute"] is False


@pytest.mark.anyio
async def test_followup_plan_is_resume_safe_and_only_returns_missing_steps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def open_status(*, job_id: int) -> dict[str, Any]:
        assert job_id == 77
        return {
            "client": BUYER,
            "status": "OPEN",
            "budget_raw": str(live_erc8183.PRICE_RAW),
            "task_spec": _task_spec(),
            "description_verification": {"valid": True},
            "open_progress": {
                "registered_policy": live_erc8183.POLICY,
                "policy_registered": True,
                "allowance_raw": "0",
                "exact_allowance": False,
            },
        }

    monkeypatch.setattr(live_erc8183, "live_job_status", open_status)
    followup = await live_erc8183.live_followup_plan(buyer=BUYER, job_id=77)

    assert followup["resume_safe"] is True
    assert [item["step"] for item in followup["transactions"]] == [
        "approve_u",
        "fund_job",
    ]


@pytest.mark.anyio
async def test_notify_is_idempotent_and_routes_by_signed_agent_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def submitted_status(*, job_id: int) -> dict[str, Any]:
        return {"status": "SUBMITTED"}

    monkeypatch.setattr(live_erc8183, "live_job_status", submitted_status)
    submitted = await live_erc8183.notify_live_agent(tmp_path, job_id=77)
    assert submitted["status"] == "already_submitted"

    async def funded_status(*, job_id: int) -> dict[str, Any]:
        return {
            "status": "FUNDED",
            "budget_raw": str(live_erc8183.PRICE_RAW),
            "task_spec": _task_spec(),
        }

    monkeypatch.setattr(live_erc8183, "live_job_status", funded_status)
    monkeypatch.setattr(
        live_erc8183,
        "resolve_live_agent",
        lambda *_args, **_kwargs: {
            "operator": "Independent Provider",
            "endpoint": "https://provider.example/a2a",
        },
    )

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

        async def post(self, url: str, *, json: dict[str, Any]) -> NotifyResponse:
            assert url == "https://provider.example/a2a"
            data = json["params"]["message"]["parts"][0]["data"]
            assert data["job_id"] == 77
            return NotifyResponse()

    monkeypatch.setattr(live_erc8183.httpx, "AsyncClient", NotifyClient)
    notification = await live_erc8183.notify_live_agent(tmp_path, job_id=77)
    assert notification["status"] == "accepted"
    assert notification["erc8004_token_id"] == 42


@pytest.mark.anyio
async def test_delivery_hash_verification_and_dispute_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "version": 1,
        "job_id": 77,
        "chain_id": 56,
        "contracts": {
            "commerce": live_erc8183.COMMERCE,
            "router": live_erc8183.ROUTER,
            "policy": live_erc8183.POLICY,
        },
        "response": {"content": "Evidence-backed grid report", "content_type": "text/plain"},
        "metadata": {"generator": "test"},
    }
    deliverable_hash = f"0x{keccak(text=canonical_json(manifest)).hex()}"

    async def submitted_status(*, job_id: int) -> dict[str, Any]:
        return {
            "status": "SUBMITTED",
            "provider": PROVIDER,
            "client": BUYER,
            "deliverable_hash": deliverable_hash,
            "task_spec": _task_spec(),
            "description": {"terms": {"success_criteria": ["Cite current evidence"]}},
            "can_settle": False,
            "can_dispute": True,
            "review_window_closed": False,
            "seconds_until_settle": 600,
            "policy_verdict": "UNDECIDED",
            "disputed": False,
        }

    async def pointer(_job_id: int, _expected_hash: str) -> dict[str, Any]:
        return {
            "deliverable_url": "ipfs://example/manifest.json",
            "deliverable_hash": deliverable_hash,
            "submitted_at": 100,
            "block_number": 200,
            "transaction_hash": "0x" + "03" * 32,
        }

    async def fetcher(_url: str, _max_bytes: int) -> tuple[dict[str, Any], str]:
        return manifest, "https://ipfs.io/ipfs/example/manifest.json"

    monkeypatch.setattr(live_erc8183, "live_job_status", submitted_status)
    monkeypatch.setattr(live_erc8183, "_delivery_pointer", pointer)

    delivery = await live_erc8183.live_delivery(job_id=77, fetch_manifest=fetcher)
    assert delivery["verification"]["hash_matches"] is True
    assert delivery["verification"]["content"] == "Evidence-backed grid report"
    assert delivery["settlement"]["can_dispute"] is True

    dispute = await live_erc8183.live_dispute_plan(buyer=BUYER, job_id=77)
    assert dispute["transaction"]["to"] == live_erc8183.POLICY
    assert dispute["transaction"]["step"] == "dispute_job"


@pytest.mark.anyio
async def test_settle_refund_and_verified_receipt_plans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def submitted_status(*, job_id: int) -> dict[str, Any]:
        return {
            "completed": False,
            "status": "SUBMITTED",
            "can_settle": True,
            "policy_verdict": "APPROVE",
            "review_window_closed": True,
        }

    monkeypatch.setattr(live_erc8183, "live_job_status", submitted_status)
    settlement = await live_erc8183.live_settle_plan(job_id=77)
    assert settlement["transaction"]["to"] == live_erc8183.ROUTER

    async def expired_status(*, job_id: int) -> dict[str, Any]:
        return {"can_refund": True}

    monkeypatch.setattr(live_erc8183, "live_job_status", expired_status)
    refund = await live_erc8183.live_refund_plan(job_id=77)
    assert refund["transaction"]["to"] == live_erc8183.COMMERCE

    async def completed_status(*, job_id: int) -> dict[str, Any]:
        return {
            "status": "COMPLETED",
            "provider": PROVIDER,
            "client": BUYER,
            "task_spec": _task_spec(),
            "description_verification": {"valid": True, "negotiation_hash": "0x" + "01" * 32},
        }

    async def completed_delivery(*, job_id: int) -> dict[str, Any]:
        return {
            "manifest_url": "https://storage.example/manifest.json",
            "manifest": {"response": {"content": "done"}},
            "verification": {"hash_matches": True},
        }

    async def completion_log(**_kwargs: Any) -> dict[str, Any]:
        return {
            "transactionHash": "0x" + "04" * 32,
            "blockNumber": "0x64",
        }

    async def payment(_hash: str, *, provider: str) -> int | None:
        return live_erc8183.PRICE_RAW if provider.lower() == PROVIDER.lower() else None

    monkeypatch.setattr(live_erc8183, "live_job_status", completed_status)
    monkeypatch.setattr(live_erc8183, "live_delivery", completed_delivery)
    monkeypatch.setattr(live_erc8183, "_find_event_log", completion_log)
    monkeypatch.setattr(live_erc8183, "_verified_payment", payment)

    receipt = await live_erc8183.build_verified_receipt(job_id=77)
    assert receipt["verification_status"] == "mainnet_verified"
    assert receipt["paid"] is True
    assert receipt["erc8004_token_id"] == 42
