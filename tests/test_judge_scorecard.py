from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proofops.judging.scorecard import build_judge_scorecard


def _write_json(root: Path, relative: str, payload: dict[str, Any]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class JudgeScorecardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        categories = (
            ("rebalancing", "rebalance_plan", 1),
            ("grid_trading", "grid_plan", 2),
            ("yield_optimisation", "yield_plan", 3),
            ("health_factor_monitoring", "health_factor", 4),
        )
        _write_json(
            self.root,
            "evidence/marketplace/live-agent-catalog.json",
            {
                "evidence_mode": "live",
                "observed_at": "2026-08-31T00:00:00Z",
                "operator": "one-provider",
                "a2a_endpoint": "https://provider.example/a2a",
                "agents": [
                    {
                        "category": category,
                        "skill_id": skill,
                        "token_id": token_id,
                        "required_inputs": {"value": "number"},
                        "created_tx_hash": "0x" + f"{token_id:064x}",
                    }
                    for category, skill, token_id in categories
                ],
            },
        )
        steps = (
            "create_job",
            "register_job",
            "set_budget",
            "approve_u",
            "fund_job",
            "submit_delivery",
            "settle_job",
        )
        _write_json(
            self.root,
            "evidence/sponsor-integration/erc8183-job-808.json",
            {
                "chain_id": 97,
                "transactions": [
                    {
                        "step": step,
                        "receipt_status": 1,
                        "tx_hash": "0x" + f"{index:064x}",
                    }
                    for index, step in enumerate(steps, start=10)
                ],
                "verification": {
                    "completed": True,
                    "provider_payment_transfer_observed": True,
                },
            },
        )
        _write_json(
            self.root,
            "evidence/termix/agent-advantage-report.json",
            {"evidence_mode": "live", "tasks": [{}, {}, {}]},
        )
        _write_json(
            self.root,
            "evidence/pancakeswap/live-benefit-report.json",
            {
                "evidence_mode": "live",
                "measurable_benefit": "same-block route improvement",
            },
        )
        sources = {
            "apps/web/live-hire.html": "live hire",
            "src/proofops/services/live_erc8183.py": (
                "safehire-external-hire-v2 verify_job_description live_delivery "
                "live_dispute_plan build_verified_receipt"
            ),
            "src/proofops/services/live_agent_market.py": (
                "verify_negotiation_envelope quote_verification agent_token_id"
            ),
        }
        for relative, content in sources.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.submission = {
            "ready": True,
            "checks": [
                {"check_id": "live_bsc_market_catalog", "passed": True},
                {"check_id": "termix_live_advantage_report", "passed": True},
                {"check_id": "pancakeswap_live_benefit", "passed": True},
            ],
        }

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_scorecard_keeps_all_four_categories_at_equal_depth(self) -> None:
        scorecard = build_judge_scorecard(
            self.root,
            self.submission,
            generated_at=datetime(2026, 8, 31, tzinfo=UTC),
        )
        parity = scorecard["category_parity"]
        self.assertEqual(len(parity), 4)
        self.assertEqual({row["status"] for row in parity}, {"ready"})
        self.assertEqual(len({row["depth_coverage"] for row in parity}), 1)

    def test_scorecard_does_not_invent_an_official_numeric_score(self) -> None:
        scorecard = build_judge_scorecard(self.root, self.submission)
        self.assertFalse(scorecard["official_rubric"]["numeric_weights_published"])
        self.assertNotIn("official_score", scorecard)
        self.assertEqual(scorecard["readiness"]["winner_readiness"], "conditional")

    def test_real_world_gaps_remain_visible(self) -> None:
        scorecard = build_judge_scorecard(self.root, self.submission)
        self.assertEqual(scorecard["main_track"]["functionality"]["status"], "conditional")
        self.assertEqual(scorecard["main_track"]["data_quality"]["status"], "conditional")
        self.assertEqual(scorecard["main_track"]["agent_diversity"]["status"], "conditional")
        self.assertEqual(scorecard["partner_tracks"]["altana"]["status"], "not_claimed")
        manual = {item["id"]: item["status"] for item in scorecard["manual_gates"]}
        self.assertEqual(manual["external_paid_delivery"], "manual_required")
        self.assertEqual(manual["independent_blind_review"], "manual_required")
        self.assertEqual(manual["second_operator"], "manual_required")
