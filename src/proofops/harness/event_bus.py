from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from proofops.domain.canonical import redact_secrets

EventHandler = Callable[["HarnessEvent"], Awaitable[None]]


@dataclass(frozen=True)
class HarnessEvent:
    event_type: str
    payload: Mapping[str, Any]
    occurred_at: datetime

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "payload": dict(self.payload),
            "occurred_at": self.occurred_at.isoformat(),
        }


class EventBus:
    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        self._handlers.setdefault(event_type, []).append(handler)

        def unsubscribe() -> None:
            handlers = self._handlers.get(event_type, [])
            if handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    async def emit(self, event_type: str, payload: Mapping[str, Any]) -> None:
        event = HarnessEvent(
            event_type=event_type,
            payload=redact_secrets(dict(payload)),
            occurred_at=datetime.now(UTC),
        )
        async with self._lock:
            handlers = list(self._handlers.get(event_type, ())) + list(self._handlers.get("*", ()))
        for handler in handlers:
            await handler(event)
