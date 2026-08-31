from __future__ import annotations

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi.testclient import TestClient

from apps.api.main import app
from proofops.domain.errors import AdapterUnavailableError


def _wallet_session(client: TestClient) -> tuple[str, str]:
    account = Account.create()
    challenge_response = client.post("/api/auth/challenge", json={"owner": account.address})
    assert challenge_response.status_code == 200
    challenge = challenge_response.json()
    signature = (
        "0x"
        + Account.sign_message(
            encode_defunct(text=challenge["message"]), account.key
        ).signature.hex()
    )
    verify_response = client.post(
        "/api/auth/verify",
        json={
            "owner": account.address,
            "message": challenge["message"],
            "signature": signature,
        },
    )
    assert verify_response.status_code == 200
    return account.address.lower(), verify_response.json()["session_token"]


def test_public_agent_card_and_invoke(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))

    with TestClient(app) as client:
        agents = client.get("/api/agents")
        card = client.get("/agents/lp-guardian-demo")
        invoke = client.post(
            "/api/agents/lp-guardian-demo/invoke",
            json={"input": card.json()["example_input"]},
        )

    assert agents.status_code == 200
    assert len(agents.json()["agents"]) == 4
    assert card.status_code == 200
    assert card.json()["protocol_version"] == "proofops-agent/1.0"
    assert invoke.status_code == 200
    assert invoke.json()["agent_id"] == "lp-guardian-demo"


def test_public_marketplace_a2a_card_and_preview(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://safehire.example.com")

    with TestClient(app) as client:
        card = client.get("/.well-known/agent-card.json")
        example = client.get("/agents/grid-sentinel-demo").json()["example_input"]
        invoke = client.post(
            "/a2a",
            json={
                "jsonrpc": "2.0",
                "id": "preview-1",
                "method": "message/send",
                "params": {
                    "message": {
                        "role": "user",
                        "messageId": "preview-message-1",
                        "parts": [
                            {
                                "kind": "data",
                                "data": {
                                    "skill": "preview",
                                    "agent_id": "grid-sentinel-demo",
                                    "input": example,
                                },
                            }
                        ],
                    }
                },
            },
        )

    assert card.status_code == 200
    assert card.json()["url"] == "https://safehire.example.com/a2a"
    assert {skill["id"] for skill in card.json()["skills"]} == {
        "list_live_agents",
        "preview",
        "public_proof",
    }
    assert invoke.status_code == 200
    assert invoke.json()["id"] == "preview-1"
    assert invoke.json()["result"]["agent_id"] == "grid-sentinel-demo"
    assert invoke.json()["result"]["action"] == "propose_grid"
    assert "no wallet signature" in invoke.json()["result"]["evidence_boundary"]


def test_wallet_hire_approve_execute_and_revoke_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))
    monkeypatch.setenv("EXECUTION_MODE", "demo")

    with TestClient(app) as client:
        owner, token = _wallet_session(client)
        headers = {"Authorization": f"Bearer {token}"}
        card = client.get("/agents/hf-shield-demo").json()
        hire = client.post(
            "/api/agents/hf-shield-demo/hire",
            headers=headers,
            json={
                "owner": owner,
                "chain_id": 97,
                "allowed_targets": ["http://localhost:8000/agents/hf-shield-demo"],
                "allowed_methods": ["invoke"],
                "max_value_usd": 100,
                "daily_value_usd": 300,
                "max_slippage_bps": 100,
                "ttl_minutes": 60,
                "request": card["example_input"],
                "idempotency_key": "hire-api-flow-0001",
            },
        )
        assert hire.status_code == 200, hire.text
        payload = hire.json()
        task_id = payload["task"]["task_id"]
        policy_id = payload["policy"]["policy_id"]
        assert payload["task"]["state"] == "approval_required"

        approve = client.post(f"/api/tasks/{task_id}/approve", headers=headers)
        assert approve.status_code == 200, approve.text
        execute = client.post(
            f"/api/tasks/{task_id}/execute",
            headers=headers,
            json={
                "idempotency_key": "execute-api-flow-0001",
                "chain_id": 97,
                "target": "http://localhost:8000/agents/hf-shield-demo",
                "method": "invoke",
                "value_usd": 100,
                "slippage_bps": 100,
                "mode": "demo",
                "source": "demo_fixture",
            },
        )
        assert execute.status_code == 200, execute.text
        receipt = execute.json()["receipt"]
        assert execute.json()["state"] == "succeeded"
        assert receipt["source"] == "demo_fixture"
        assert receipt["result"]["status"] == "simulated_demo_execution"

        revoke = client.post(f"/api/permissions/{policy_id}/revoke", headers=headers)
        assert revoke.status_code == 200
        assert revoke.json()["revoked"] is True


def test_wallet_protected_route_rejects_anonymous_user(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))

    with TestClient(app) as client:
        response = client.get("/api/permissions")

    assert response.status_code == 401
    assert response.json()["detail"] == "wallet_session_required"


def test_network_query_coerces_chain_id_to_integer(tmp_path, monkeypatch) -> None:
    class FakeNetwork:
        async def status(self, chain_id: int):
            assert isinstance(chain_id, int)
            return {"chain_id": chain_id, "block_number": 123}

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))

    with TestClient(app) as client:
        client.app.state.application.network = FakeNetwork()
        response = client.get("/api/network?chain_id=97")

    assert response.status_code == 200
    assert response.json() == {"chain_id": 97, "block_number": 123}


def test_network_failure_is_a_stable_503(tmp_path, monkeypatch) -> None:
    class UnavailableNetwork:
        async def status(self, _chain_id: int):
            raise AdapterUnavailableError("BSC RPC unavailable")

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))

    with TestClient(app) as client:
        client.app.state.application.network = UnavailableNetwork()
        response = client.get("/api/network?chain_id=97")

    assert response.status_code == 503
    assert response.json() == {
        "error": "upstream_unavailable",
        "message": "BSC RPC unavailable",
    }


def test_browser_deployment_plan_is_unsigned_and_testnet_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))
    monkeypatch.setenv("APP_ENV", "development")

    with TestClient(app) as client:
        base = client.get("/api/dev/contracts/deployment-plan")
        policy = client.post(
            "/api/dev/contracts/scoped-policy-plan",
            json={
                "owner": "0xe144264e2b71ec885cb10a10c6881b45fdf54f5f",
                "registry_address": "0x1111111111111111111111111111111111111111",
                "expires_at": 2_000_000_000,
            },
        )

    assert base.status_code == 200, base.text
    assert base.json()["chain_id"] == 97
    assert base.json()["funding"] == {
        "kind": "funding",
        "contract_name": "FundAgentWallet",
        "to": "0x7ca564102be3C107EdA9075F490a9bB1bb74daED",
        "value": "0xb1a2bc2ec50000",
        "value_wei": "50000000000000000",
        "value_display": "0.05 tBNB",
    }
    assert [item["contract_name"] for item in base.json()["transactions"]] == [
        "AgentRegistry",
        "EvidenceAnchor",
    ]
    assert all(item["data"].startswith("0x") for item in base.json()["transactions"])
    assert base.json()["asset_boundary"]["deployment_spends_hiring_asset"] is False
    assert policy.status_code == 200, policy.text
    assert policy.json()["chain_id"] == 97
    assert policy.json()["value"] == "0x0"
    assert policy.json()["policy"]["max_total_value_wei"] == "0"
    assert policy.json()["policy"]["revocable"] is True


def test_browser_deployment_plan_is_hidden_in_production(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_API_KEY", "production-test-admin")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://safehire.example.com")

    with TestClient(app) as client:
        response = client.get("/api/dev/contracts/deployment-plan")

    assert response.status_code == 404
