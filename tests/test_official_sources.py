from __future__ import annotations

import httpx
import pytest

from proofops.domain.errors import AdapterUnavailableError
from proofops.integrations.official_sources import OfficialSourceClient


@pytest.mark.anyio
async def test_official_sources_validate_and_label_responses() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        if "8004scan" in request.url.host:
            return httpx.Response(200, json={"items": [{"chain_id": 97}], "total": 1})
        if "venus" in request.url.host:
            return httpx.Response(200, json={"pools": [{"address": "0xpool"}]})
        if "lista" in request.url.host:
            return httpx.Response(200, json={"data": [{"address": "0xvault"}]})
        raise AssertionError(f"unexpected URL: {request.url}")

    client = OfficialSourceClient(transport=httpx.MockTransport(handler))

    scan = await client.scan8004_agents(limit=1)
    venus = await client.venus_pools()
    lista = await client.lista_vaults(limit=1)

    assert scan["source"] == "8004scan_official_api"
    assert scan["items"][0]["chain_id"] == 97
    assert venus["pools"][0]["address"] == "0xpool"
    assert lista["vaults"][0]["address"] == "0xvault"


@pytest.mark.anyio
async def test_pancake_position_fails_closed_without_graph_key() -> None:
    client = OfficialSourceClient()

    with pytest.raises(AdapterUnavailableError, match="THE_GRAPH_API_KEY"):
        await client.pancake_position("42")


@pytest.mark.anyio
async def test_unexpected_schema_is_not_replaced_by_fixture() -> None:
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={"unexpected": True}))
    client = OfficialSourceClient(transport=transport)

    with pytest.raises(AdapterUnavailableError, match="unexpected pools schema"):
        await client.venus_pools()


@pytest.mark.anyio
async def test_provider_intake_builds_read_only_review_dossier() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/agents/56/304494")
        return httpx.Response(
            200,
            json={
                "token_id": "304494",
                "name": "Independent Grid Agent",
                "description": "Creates bounded grid trading plans",
                "owner_address": "0x1111111111111111111111111111111111111111",
                "agent_wallet": "0x2222222222222222222222222222222222222222",
                "a2a_endpoint": "https://agent.example/a2a",
                "supported_protocols": ["A2A"],
                "is_active": True,
                "is_endpoint_verified": True,
                "total_feedbacks": 2,
                "total_validations": 3,
                "successful_validations": 2,
                "total_score": 4.2,
                "quality_score": 4.5,
                "health_score": 4,
                "metadata_completeness_score": 5,
            },
        )

    client = OfficialSourceClient(transport=httpx.MockTransport(handler))
    result = await client.validate_agent_intake(chain_id=56, token_id=304494)

    assert result["eligible_for_review"] is True
    assert result["listing_created"] is False
    assert result["agent"]["matched_categories"] == ["grid_trading"]
    assert all(check["passed"] for check in result["checks"])
    assert "read-only intake preview" in result["trust_boundary"]
