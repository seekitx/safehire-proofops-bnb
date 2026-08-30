from __future__ import annotations

from typing import Any

from .event_bus import HarnessEvent


class TraceSubscriber:
    """Bridges runtime events into the tamper-evident evidence ledger."""

    def __init__(self, ledger: Any) -> None:
        self._ledger = ledger

    async def __call__(self, event: HarnessEvent) -> None:
        self._ledger.append(
            kind="harness_trace",
            source="runtime",
            payload=event.to_dict(),
        )
