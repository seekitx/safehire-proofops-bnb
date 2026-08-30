from __future__ import annotations

import unittest

from proofops.domain.models import DataSource, EvidenceLevel
from proofops.plugins.agent_proof import AgentProofScorer
from tests.helpers import sample_agent


class AgentProofTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scorer = AgentProofScorer()

    def test_testnet_evidence_caps_score_at_75(self) -> None:
        result = self.scorer.score(sample_agent())
        self.assertEqual(result.evidence_cap, 75.0)
        self.assertLessEqual(result.final_score, 75.0)

    def test_fixture_can_never_look_production_grade(self) -> None:
        agent = sample_agent(
            source=DataSource.DEMO_FIXTURE,
            level=EvidenceLevel.VERIFIED_TRACK_RECORD,
        )
        result = self.scorer.score(agent)
        self.assertEqual(result.evidence_cap, 30.0)
        self.assertLessEqual(result.final_score, 30.0)

    def test_not_live_reduces_cap(self) -> None:
        result = self.scorer.score(sample_agent(live=False))
        self.assertLessEqual(result.evidence_cap, 50.0)
        self.assertTrue(any("not marked live" in item for item in result.penalties))

    def test_mainnet_verified_track_record_can_reach_full_cap(self) -> None:
        result = self.scorer.score(
            sample_agent(source=DataSource.LIVE_ONCHAIN, level=EvidenceLevel.VERIFIED_TRACK_RECORD)
        )
        self.assertEqual(result.evidence_cap, 100.0)
        self.assertGreater(result.final_score, 85.0)
