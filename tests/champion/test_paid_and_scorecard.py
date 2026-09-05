from __future__ import annotations

import asyncio
import copy
import hashlib
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from proofops.decision.paid import COMMERCE, ROUTER, TOKEN, verify_delivery
from proofops.judging.scorecard import build_judge_scorecard

BUYER, PROVIDER = "0x" + "a" * 40, "0x" + "b" * 40
TX, BLOCK = "0x" + "c" * 64, "0x" + "d" * 64
OUTPUT = b"Artificial test preimage; no live payment occurred."
CLAIM = {"chain_id": 56, "job_id": 123, "buyer": BUYER, "provider": PROVIDER, "token_id": 302258,
         "skill_id": "grid_plan", "settlement_tx_hash": TX, "commitment_scheme": "keccak256_exact_utf8_bytes"}
AGENTS = [{"token_id": 302258, "skill_id": "grid_plan"}]


class FakeReader:
    """Synthetic decoded transport; intentionally not a test of production Keccak/ABI."""
    def __init__(self):
        self.snapshot = {"chain_id": 56, "status": 1, "tx_hash": TX, "to": ROUTER,
                         "function": "settle(uint256,bytes)", "job_id": 123,
                         "confirmations": 12, "block_number": 100, "block_hash": BLOCK,
                         "transfers": [{"token": TOKEN, "from": COMMERCE, "to": PROVIDER, "amount_raw": 100}]}
        self.record = {"job_id": 123, "status": "COMPLETED", "buyer": BUYER, "provider": PROVIDER,
                       "budget_raw": 100, "deliverable_hash": self.commitment(OUTPUT),
                       "description": {"schema_version": "safehire-live-hire-v1", "service": "grid_plan",
                                       "erc8004_token_id": 302258, "provider": PROVIDER, "price_raw": "100"}}
        self.canonical = BLOCK
        self.read_at = None
        self.agent_identity = {"wallet": PROVIDER, "owner": PROVIDER}
    def commitment(self, payload):
        return "0x" + hashlib.sha256(payload).hexdigest()
    async def settlement(self, tx_hash):
        return self.snapshot
    async def job(self, job_id, block_hash):
        self.read_at = block_hash
        return self.record
    async def canonical_block_hash(self, block_number):
        return self.canonical
    async def identity(self, token_id, block_hash):
        return self.agent_identity


def verified(reader=None):
    return asyncio.run(verify_delivery(copy.deepcopy(CLAIM), OUTPUT, reader or FakeReader(), reviewed_agents=AGENTS))


def test_paid_replay_binds_block_output_job_and_payment():
    reader = FakeReader()
    result = verified(reader)
    assert result.provider_payment_raw == 100
    assert reader.read_at == BLOCK
    assert result.to_dict()["quality_verified"] is False
    assert result.to_dict()["business_independence_verified"] is False


@pytest.mark.parametrize("field,value", [("chain_id", 97), ("status", 0), ("tx_hash", "0x" + "e"*64),
    ("to", PROVIDER), ("job_id", 999), ("function", "approve(address,uint256)"),
    ("confirmations", 11), ("confirmations", True), ("block_hash", "0x"), ("transfers", [])])
def test_arbitrary_successful_transaction_is_not_paid_proof(field, value):
    reader = FakeReader()
    reader.snapshot[field] = value
    with pytest.raises(ValueError):
        verified(reader)


@pytest.mark.parametrize("field,value", [("status", "FUNDED"), ("job_id", 999), ("buyer", PROVIDER),
    ("provider", BUYER), ("budget_raw", 0), ("deliverable_hash", "0x" + "f"*64)])
def test_wrong_job_data_fails(field, value):
    reader = FakeReader()
    reader.record[field] = value
    with pytest.raises(ValueError):
        verified(reader)


@pytest.mark.parametrize("field,value", [("service", "health_factor"), ("erc8004_token_id", 1),
    ("provider", BUYER), ("price_raw", "200"), ("schema_version", "anything")])
def test_job_description_must_bind_catalog_and_price(field, value):
    reader = FakeReader()
    reader.record["description"][field] = value
    with pytest.raises(ValueError):
        verified(reader)


@pytest.mark.parametrize("field,value", [("token", BUYER), ("from", BUYER), ("to", BUYER),
    ("amount_raw", 101), ("amount_raw", -1), ("amount_raw", True)])
def test_unrelated_or_invalid_transfer_rejected(field, value):
    reader = FakeReader()
    reader.snapshot["transfers"][0][field] = value
    with pytest.raises(ValueError):
        verified(reader)


def test_reorganization_rejected():
    reader = FakeReader()
    reader.canonical = "0x" + "f"*64
    with pytest.raises(ValueError, match="reorganized"):
        verified(reader)


def test_modified_output_rejected():
    with pytest.raises(ValueError, match="commitment"):
        asyncio.run(verify_delivery(CLAIM, OUTPUT + b"tampered", FakeReader(), reviewed_agents=AGENTS))


def test_self_hire_excluded():
    claim = {**CLAIM, "provider": BUYER}
    with pytest.raises(ValueError, match="self-hire"):
        asyncio.run(verify_delivery(claim, OUTPUT, FakeReader(), reviewed_agents=AGENTS))


def test_legacy_paid_true_json_does_not_complete_gate(tmp_path):
    directory = tmp_path / "evidence/marketplace/paid-deliveries"
    directory.mkdir(parents=True)
    (directory / "fake.json").write_text(json.dumps({"evidence_mode": "live", "chain_id": 56,
        "external_provider": True, "paid": True, "settlement_tx_hash": TX}))
    report = build_judge_scorecard(tmp_path)
    gate = next(gate for gate in report["manual_gates"] if gate["id"] == "external_paid_delivery")
    assert gate["status"] == "manual_required"
    assert report["evidence_integrity"]["paid_candidate_files"] == 1
    assert report["evidence_integrity"]["freshly_replayed_paid_deliveries"] == 0


def test_fresh_typed_replay_counts_once_and_expires(tmp_path):
    result = verified()
    now = datetime.now(UTC)
    report = build_judge_scorecard(tmp_path, generated_at=now, verified_deliveries=(result, result))
    assert report["evidence_integrity"]["freshly_replayed_paid_deliveries"] == 1
    stale = replace(result, verified_at=(now-timedelta(minutes=6)).isoformat())
    report = build_judge_scorecard(tmp_path, generated_at=now, verified_deliveries=(stale,))
    assert report["evidence_integrity"]["freshly_replayed_paid_deliveries"] == 0


def test_independent_review_boolean_is_not_authentication(tmp_path):
    directory = tmp_path / "evidence/termix/v2/reviews"
    directory.mkdir(parents=True)
    for index in range(3):
        (directory / f"review-{index}.json").write_text(json.dumps({"evidence_mode": "live",
             "review_mode": "blind", "independent_reviewer": True, "task_id": f"task-{index}"}))
    report = build_judge_scorecard(tmp_path)
    assert report["partner_tracks"]["termix"]["independent_blind_reviews"] == 0
    assert report["evidence_integrity"]["blind_review_candidate_files"] == 3


def test_nonempty_ancient_timestamp_is_not_fresh(tmp_path):
    folder = tmp_path / "evidence/marketplace"
    folder.mkdir(parents=True)
    (folder / "live-agent-catalog.json").write_text(json.dumps({"observed_at": "2020-01-01T00:00:00Z", "agents": []}))
    result = build_judge_scorecard(tmp_path)
    assert result["evidence_integrity"]["catalog_freshness"]["status"] == "stale"
    assert not result["main_track"]["data_quality"]["checks"]["freshness_timestamp"]


@pytest.mark.parametrize("field", ["owner", "wallet"])
def test_false_registry_binding_or_agent_owner_self_hire_rejected(field):
    reader = FakeReader()
    reader.agent_identity[field] = BUYER
    with pytest.raises(ValueError):
        verified(reader)
