from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proofops.domain.models import LpPosition
from proofops.plugins.adversarial import (
    AdversarialCouncil,
    CouncilRole,
    Proposal,
)
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

    def test_default_ten_role_debate_accepts_with_visible_manual_gaps(self) -> None:
        decision = AdversarialCouncil(self.ledger).review(Proposal.safehire_default())
        self.assertTrue(decision.accepted)
        self.assertEqual(len(decision.arguments), len(CouncilRole))
        self.assertEqual(len(CouncilRole), 10)
        self.assertFalse(decision.vetoes)
        changes = {
            change
            for argument in decision.arguments
            for change in argument.required_changes
        }
        self.assertIn("Onboard a second independent ERC-8004 provider.", changes)
        self.assertIn(
            "Complete one bounded external paid hire and attach the delivery receipt.",
            changes,
        )

    def test_security_gap_causes_veto(self) -> None:
        proposal = Proposal.safehire_default()
        unsafe = Proposal(**{**proposal.__dict__, "safety_controls": ("human approval",)})
        decision = AdversarialCouncil(self.ledger).review(unsafe)
        self.assertFalse(decision.accepted)
        self.assertIn("security_red_team", decision.vetoes)

    def test_missing_category_depth_causes_diversity_veto(self) -> None:
        proposal = Proposal.safehire_default()
        shallow = Proposal(
            **{
                **proposal.__dict__,
                "category_depth": (
                    "rebalancing",
                    "grid_trading",
                    "yield_optimisation",
                ),
            }
        )
        decision = AdversarialCouncil(self.ledger).review(shallow)
        self.assertFalse(decision.accepted)
        self.assertIn("bnb_diversity_judge", decision.vetoes)

    def test_fake_live_plan_causes_bnb_veto(self) -> None:
        proposal = Proposal.safehire_default()
        no_live = Proposal(**{**proposal.__dict__, "live_bsc_plan": False})
        decision = AdversarialCouncil(self.ledger).review(no_live)
        self.assertFalse(decision.accepted)
        self.assertIn("bnb_main_judge", decision.vetoes)

    def test_altana_logo_without_session_is_challenged_not_counted(self) -> None:
        proposal = Proposal.safehire_default()
        claim = Proposal(
            **{
                **proposal.__dict__,
                "sponsor_integrations": (*proposal.sponsor_integrations, "Altana"),
            }
        )
        decision = AdversarialCouncil(self.ledger).review(claim)
        altana = next(
            item
            for item in decision.arguments
            if item.role == CouncilRole.ALTANA_SESSION_REVIEWER
        )
        self.assertTrue(altana.attacks)
        self.assertIn("session-key", altana.attacks[0])
