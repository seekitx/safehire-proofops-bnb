import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


def test_public_human_pairs_preserve_bound_inputs_and_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "api.db"))
    monkeypatch.setenv("EVIDENCE_LEDGER_PATH", str(tmp_path / "evidence.jsonl"))
    root = Path(__file__).resolve().parents[1]
    with TestClient(app) as client:
        response = client.get("/api/evidence/termix/human-study")
        assert response.status_code == 200
        report = response.json()
        assert report["independent_review"] == "not_available"
        assert report["quality_score"] is None
        assert len({row["task_id"] for row in report["pairs"]}) == 3
        for row in report["pairs"]:
            task_id = row["task_id"]
            pair_response = client.get(row["pair_url"])
            assert pair_response.status_code == 200
            pair = pair_response.json()
            raw_pair = (root / f"evidence/termix/human-study/{task_id}.json").read_bytes()
            assert hashlib.sha256(raw_pair).hexdigest() == row["pair_sha256"]
            task_bytes = (root / f"evidence/termix/tasks/{task_id}.json").read_bytes()
            assert hashlib.sha256(task_bytes).hexdigest() == row["task_raw_sha256"]
            assert pair["task_snapshot"] == json.loads(task_bytes)
            assert pair["manual"]["task_snapshot"] == pair["agent"]["task_snapshot"] == pair["task_snapshot"]
            agent_bytes = (root / f"evidence/termix/raw/{task_id}/agent-output.json").read_bytes()
            assert hashlib.sha256(agent_bytes).hexdigest() == row["agent_raw_sha256"]
            assert pair["agent"] == json.loads(agent_bytes)
            manual = pair["manual"]
            assert "operator" not in manual
            assert manual["redactions"] == ["operator"]
            assert manual["evidence_mode"] == "human_timed_manual_run"
            assert manual["output"].strip()
            assert manual["duration_seconds"] == row["human_seconds"] > 0
            assert manual["original_private_file_sha256"] == row["manual_raw_sha256"]
        # Excluded AI-assisted practice and repeated trials must not become extra evidence.
        assert client.get("/api/evidence/termix/human-study/live-20260908-health").status_code == 404
        assert client.get("/api/evidence/termix/human-study/unknown").status_code == 404
