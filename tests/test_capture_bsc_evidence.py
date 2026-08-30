from __future__ import annotations

import json

import pytest

from scripts import capture_bsc_evidence


@pytest.mark.anyio
async def test_capture_requires_successful_live_receipt(tmp_path, monkeypatch) -> None:
    class FakeNetwork:
        def __init__(self, **_kwargs) -> None:
            pass

        async def verify_transaction(self, chain_id: int, tx_hash: str):
            return {
                "found": True,
                "successful": True,
                "receipt": {
                    "blockNumber": "0x10",
                    "gasUsed": "0x5208",
                    "from": "0x" + "1" * 40,
                    "to": "0x" + "2" * 40,
                },
                "explorer_url": f"https://testnet.bscscan.com/tx/{tx_hash}",
                "observed_at": "2026-08-30T10:00:00+08:00",
            }

    monkeypatch.setattr(capture_bsc_evidence, "ROOT", tmp_path)
    monkeypatch.setattr(capture_bsc_evidence, "BscNetworkService", FakeNetwork)
    tx_hash = "0x" + "a" * 64

    path = await capture_bsc_evidence.capture(97, tx_hash, "bounded-test-swap")

    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["evidence_mode"] == "live"
    assert record["successful"] is True
    assert record["gas_used"] == 21000
    with pytest.raises(FileExistsError):
        await capture_bsc_evidence.capture(97, tx_hash, "bounded-test-swap")
