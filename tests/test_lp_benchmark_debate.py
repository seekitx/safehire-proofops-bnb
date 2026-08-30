from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proofops.domain.models import LpPosition
from proofops.plugins.adversarial import AdversarialCouncil, Proposal
from proofops.plugins.benchmark import BenchmarkRunner
from proofops.plugins.evidence import EvidenceLedger
from proofops.plugins.lp_guardian import LpGuardianPolicy


class LpBenchmarkDebateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.ledger = EvidenceLedger(Path(self.tmp.name) / "evidence.jsonl")
        self.policy = LpGuardianPolicy()

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_lp_holds_when_cost_not_justified(self) -> None:
        result = self.policy.simulate(LpPosition(610, 500, 700, 0.2, 0.01, 100_000, 50.0), 1_000)
        self.assertFalse(result.should_rebalance)
        self.assertTrue(result.current_in_range)

    def test_lp_rebalances_when_outside_and_benefit_exceeds_cost(self) -> None:
        result = self.policy.simulate(
            LpPosition(720, 500, 700, 0.3, 0.50, 1_000_000, 0.10, 1.0), 10_000
        )
        self.assertTrue(result.should_rebalance)
        self.assertFalse(result.current_in_range)

    def test_three_benchmarks_keep_raw_outputs(self) -> None:
        results = BenchmarkRunner(self.policy, self.ledger).run_all()
        self.assertEqual(len(results), 3)
        for result in results:
            data = result.to_dict()
            self.assertIn("manual", data)
            self.assertIn("agent", data)
            self.assertIn("advantage", data)
            self.assertTrue(data["limitations"])

    def test_default_seven_role_debate_accepts(self) -> None:
        decision = AdversarialCouncil(self.ledger).review(Proposal.safehire_default())
        self.assertTrue(decision.accepted)
        self.assertEqual(len(decision.arguments), 7)
        self.assertFalse(decision.vetoes)

    def test_security_gap_causes_veto(self) -> None:
        proposal = Proposal.safehire_default()
        unsafe = Proposal(**{**proposal.__dict__, "safety_controls": ("human approval",)})
        decision = AdversarialCouncil(self.ledger).review(unsafe)
        self.assertFalse(decision.accepted)
        self.assertIn("security_red_team", decision.vetoes)

    def test_fake_live_plan_causes_bnb_veto(self) -> None:
        proposal = Proposal.safehire_default()
        no_live = Proposal(**{**proposal.__dict__, "live_bsc_plan": False})
        decision = AdversarialCouncil(self.ledger).review(no_live)
        self.assertFalse(decision.accepted)
        self.assertIn("bnb_main_judge", decision.vetoes)
