from __future__ import annotations

import asyncio
import copy
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from fastapi import FastAPI

from proofops.decision.market import REVIEWED, SnapshotCache, compare_market, freshness, project_market
from proofops.decision.routes import make_router

NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)


def snapshot(now=NOW):
    return {"observed_at": now.isoformat(), "source": "test_fixture", "endpoint_reachable": True,
            "operator": "one provider", "agents": [
                {"token_id": token, "skill_id": skill, "category": rule[0], "name": skill,
                 "description": "Fixture, not live observation", "currently_callable": True,
                 "created_tx_hash": "0x" + "a" * 64,
                 "market_signals": {"available": True, "owner_address": "0x" + "a" * 40,
                                    "endpoint_last_checked_at": now.isoformat()}}
                for (token, skill), rule in REVIEWED.items()]}


def test_four_skills_are_not_four_independent_providers():
    result = project_market(snapshot(), now=NOW)
    assert len(result["categories"]) == 4
    assert result["supplier_concentration"]["distinct_owner_addresses_from_index"] == 1
    assert result["supplier_concentration"]["independent_businesses_verified"] is None
    assert all(not row["capability"]["execution_proven"] for row in result["listings"])
    assert all(row["verified_paid_outcomes"] is None for row in result["listings"])


def test_portfolio_rebalance_is_not_lp_range_execution():
    result = project_market(snapshot(), now=NOW)
    row = next(row for row in result["listings"] if row["category"] == "rebalancing")
    assert not row["capability"]["category_analysis_fit"]
    assert "official_category_scope_gap" in row["evidence_gaps"]
    assert row["analysis_hire_available"]  # Correctly labeled analysis, not automatic LP reset.
    assert not row["execution_hire_available"]


@pytest.mark.parametrize("stamp", [None, "nonsense", "2026-09-05T12:00:00", "2026-09-06T12:00:00Z"])
def test_bad_timestamps_never_become_fresh(stamp):
    assert freshness(stamp, NOW)["status"] == "unknown"


@pytest.mark.parametrize("age", [61, 3600, 86400])
def test_stale_probe_disables_hiring(age):
    raw = snapshot(NOW - timedelta(seconds=age))
    result = project_market(raw, now=NOW)
    assert all(not row["analysis_hire_available"] and row["hire_url"] is None for row in result["listings"])


def test_stale_index_and_fresh_probe_stay_separate():
    raw = snapshot()
    raw["agents"][0]["market_signals"]["endpoint_last_checked_at"] = "2026-08-01T00:00:00Z"
    row = next(row for row in project_market(raw, now=NOW)["listings"] if row["category"] == "rebalancing")
    assert row["probe"]["status"] == "fresh"
    assert row["index"]["freshness"]["status"] == "stale"


def test_unreviewed_provider_cannot_use_hardcoded_hire_adapter():
    raw = snapshot()
    raw["agents"][0]["token_id"] = 999999
    row = next(row for row in project_market(raw, now=NOW)["listings"] if row["id"] == "56:999999")
    assert not row["analysis_hire_available"]
    assert "provider_adapter_not_reviewed" in row["evidence_gaps"]


def test_missing_owner_does_not_create_a_fictitious_unique_supplier():
    raw = snapshot()
    for index, row in enumerate(raw["agents"]):
        row["operator"] = f"Different label {index}"
        row["market_signals"] = {"available": False}
    result = project_market(raw, now=NOW)["supplier_concentration"]
    assert result["distinct_owner_addresses_from_index"] == 0
    assert result["declared_operator_labels"] == 4
    assert result["unresolved_owner_listings"] == 4


def test_duplicate_and_invalid_ids_are_rejected():
    raw = snapshot()
    raw["agents"] += [copy.deepcopy(raw["agents"][0]), {"token_id": True}, None]
    result = project_market(raw, now=NOW)
    assert len(result["listings"]) == 4 and result["rejected_or_duplicate_rows"] == 3


@pytest.mark.parametrize("ids", [["56:304494", "56:302258"], ["56:304494"] * 2, ["56:0", "56:302258"]])
def test_invalid_comparison_rejected(ids):
    with pytest.raises(ValueError):
        compare_market(project_market(snapshot(), now=NOW), ids)


def test_same_category_comparison_does_not_invent_winner():
    raw = snapshot()
    other = copy.deepcopy(raw["agents"][0])
    other["token_id"] = 333333
    raw["agents"].append(other)
    result = compare_market(project_market(raw, now=NOW), ["56:304494", "56:333333"])
    assert result["winner"] is None and len(result["agents"]) == 2


def test_singleflight_and_copy_isolation():
    async def run():
        calls = 0
        async def load():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return snapshot()
        cache = SnapshotCache(load)
        values = await asyncio.gather(*(cache.get() for _ in range(20)))
        values[0]["agents"].clear()
        assert calls == 1 and len(values[1]["agents"]) == 4
        assert len((await cache.get())["agents"]) == 4
    asyncio.run(run())


def test_refresh_failure_preserves_original_timestamp_but_disables_hire():
    async def run():
        clock = [0.0]
        fail = [False]
        async def load():
            if fail[0]:
                raise httpx.ConnectError("unavailable")
            return snapshot()
        cache = SnapshotCache(load, clock=lambda: clock[0], ttl=20)
        await cache.get()
        fail[0] = True
        clock[0] = 21
        result = await cache.get()
        assert result["observed_at"] == NOW.isoformat()
        assert result["refresh_error"] == "ConnectError"
        assert all(not row["analysis_hire_available"] for row in project_market(result, now=NOW)["listings"])
    asyncio.run(run())


def test_cache_timeout_returns_no_invented_agents():
    async def run():
        async def load():
            await asyncio.sleep(0.1)
            return snapshot()
        value = await SnapshotCache(load, timeout=0.001).get()
        assert value["agents"] == [] and value["observed_at"] is None
    asyncio.run(run())


def test_router_filter_compare_and_all_four_previews(tmp_path):
    async def run():
        async def load():
            return snapshot(datetime.now(UTC))
        app = FastAPI()
        app.include_router(make_router(tmp_path, SnapshotCache(load)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
            response = await client.get("/api/decision/market", params={"category": "grid_trading"})
            assert response.status_code == 200 and len(response.json()["listings"]) == 1
            assert (await client.get("/api/decision/market?category=not-a-category")).status_code == 422
            assert (await client.get("/api/decision/market", params={"q": "z" * 101})).status_code == 422
            bad = await client.post("/api/decision/compare", json={"agent_ids": ["56:304494", "56:302258"]})
            assert bad.status_code == 422
            examples = (await client.get("/api/decision/examples")).json()
            assert examples["evidence_mode"] == "synthetic_examples"
            for category, payload in examples["examples"].items():
                response = await client.post("/api/decision/preview", json={"category": category, "input": payload})
                assert response.status_code == 200
                assert response.json()["trade_executed"] is False
                assert response.json()["result"]["execution_authority"] == "none_preview_only"
            response = await client.post("/api/decision/preview", json={"category": "grid_trading", "input": {}})
            assert response.status_code == 422
    asyncio.run(run())
