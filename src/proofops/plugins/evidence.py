from __future__ import annotations

import json
import os
import threading
from collections.abc import Iterator, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proofops.domain.canonical import canonical_json, redact_secrets, sha256_hex
from proofops.domain.errors import EvidenceIntegrityError
from proofops.harness.contracts import HarnessPlugin, PluginContext


@dataclass(frozen=True)
class LedgerRecord:
    index: int
    record_id: str
    occurred_at: str
    kind: str
    source: str
    payload: Mapping[str, Any]
    payload_hash: str
    previous_hash: str
    record_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EvidenceLedger:
    GENESIS_HASH = "0" * 64

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        if not self.path.exists():
            self.path.touch(mode=0o600)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    def _last(self) -> tuple[int, str]:
        last_index = -1
        last_hash = self.GENESIS_HASH
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if not raw.strip():
                    continue
                item = json.loads(raw)
                last_index = int(item["index"])
                last_hash = str(item["record_hash"])
        return last_index, last_hash

    def append(self, *, kind: str, source: str, payload: Mapping[str, Any]) -> LedgerRecord:
        clean_payload = redact_secrets(dict(payload))
        with self._lock:
            last_index, previous_hash = self._last()
            occurred_at = datetime.now(UTC).isoformat()
            payload_hash = sha256_hex(clean_payload)
            unsigned = {
                "index": last_index + 1,
                "occurred_at": occurred_at,
                "kind": kind,
                "source": source,
                "payload_hash": payload_hash,
                "previous_hash": previous_hash,
            }
            record_hash = sha256_hex(unsigned)
            record = LedgerRecord(
                index=last_index + 1,
                record_id=f"ev_{record_hash[:20]}",
                occurred_at=occurred_at,
                kind=kind,
                source=source,
                payload=clean_payload,
                payload_hash=payload_hash,
                previous_hash=previous_hash,
                record_hash=record_hash,
            )
            line = canonical_json(record.to_dict()) + "\n"
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()
                os.fsync(handle.fileno())
            return record

    def records(self) -> Iterator[LedgerRecord]:
        with self.path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                if raw.strip():
                    item = json.loads(raw)
                    yield LedgerRecord(**item)

    def verify(self) -> dict[str, Any]:
        expected_previous = self.GENESIS_HASH
        count = 0
        errors: list[str] = []
        for record in self.records():
            if record.index != count:
                errors.append(f"index mismatch at {count}: {record.index}")
            expected_payload_hash = sha256_hex(record.payload)
            if record.payload_hash != expected_payload_hash:
                errors.append(f"payload hash mismatch at {record.index}")
            if record.previous_hash != expected_previous:
                errors.append(f"previous hash mismatch at {record.index}")
            unsigned = {
                "index": record.index,
                "occurred_at": record.occurred_at,
                "kind": record.kind,
                "source": record.source,
                "payload_hash": record.payload_hash,
                "previous_hash": record.previous_hash,
            }
            expected_record_hash = sha256_hex(unsigned)
            if record.record_hash != expected_record_hash:
                errors.append(f"record hash mismatch at {record.index}")
            expected_previous = record.record_hash
            count += 1
        return {
            "valid": not errors,
            "records": count,
            "head_hash": expected_previous,
            "errors": errors,
        }

    def require_valid(self) -> None:
        result = self.verify()
        if not result["valid"]:
            raise EvidenceIntegrityError("; ".join(result["errors"]))


class EvidencePlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        raw_path = self.manifest.config.get("path") or os.getenv(
            "EVIDENCE_LEDGER_PATH", ".data/evidence.jsonl"
        )
        path = Path(str(raw_path))
        ledger = EvidenceLedger(path)
        ledger.require_valid()
        context.provide("evidence.ledger", ledger)

    async def start(self, context: PluginContext) -> None:
        ledger: EvidenceLedger = context.resolve("evidence.ledger")
        ledger.append(kind="plugin_started", source=self.manifest.plugin_id, payload={})
