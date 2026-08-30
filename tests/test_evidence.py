from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from proofops.plugins.evidence import EvidenceLedger


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "evidence.jsonl"
        self.ledger = EvidenceLedger(self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_append_and_verify_hash_chain(self) -> None:
        first = self.ledger.append(kind="one", source="test", payload={"value": 1})
        second = self.ledger.append(kind="two", source="test", payload={"value": 2})
        self.assertEqual(second.previous_hash, first.record_hash)
        result = self.ledger.verify()
        self.assertTrue(result["valid"])
        self.assertEqual(result["records"], 2)

    def test_tamper_is_detected(self) -> None:
        self.ledger.append(kind="one", source="test", payload={"value": 1})
        item = json.loads(self.path.read_text().strip())
        item["payload"]["value"] = 999
        self.path.write_text(json.dumps(item) + "\n")
        result = self.ledger.verify()
        self.assertFalse(result["valid"])
        self.assertIn("payload hash mismatch", result["errors"][0])

    def test_secrets_are_redacted(self) -> None:
        record = self.ledger.append(
            kind="secret",
            source="test",
            payload={"api_key": "do-not-store", "nested": {"password": "x"}},
        )
        self.assertEqual(record.payload["api_key"], "<redacted>")
        self.assertEqual(record.payload["nested"]["password"], "<redacted>")
