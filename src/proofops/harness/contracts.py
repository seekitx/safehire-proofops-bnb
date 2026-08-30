from __future__ import annotations

from abc import ABC
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PluginState(str, Enum):
    DISCOVERED = "discovered"
    LOADED = "loaded"
    STARTED = "started"
    STOPPED = "stopped"
    FAILED = "failed"
    UNLOADED = "unloaded"


@dataclass(frozen=True)
class PluginManifest:
    plugin_id: str
    version: str
    entrypoint: str
    provides: tuple[str, ...]
    requires: tuple[str, ...] = ()
    optional_requires: tuple[str, ...] = ()
    config: Mapping[str, Any] = field(default_factory=dict)
    enabled: bool = True
    critical: bool = False

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> PluginManifest:
        return cls(
            plugin_id=str(data["plugin_id"]),
            version=str(data.get("version", "0.1.0")),
            entrypoint=str(data["entrypoint"]),
            provides=tuple(data.get("provides", ())),
            requires=tuple(data.get("requires", ())),
            optional_requires=tuple(data.get("optional_requires", ())),
            config=dict(data.get("config", {})),
            enabled=bool(data.get("enabled", True)),
            critical=bool(data.get("critical", False)),
        )


class PluginContext:
    def __init__(self, services: dict[str, Any], emit: Callable[..., Awaitable[None]]) -> None:
        self._services = services
        self._emit = emit

    def provide(self, capability: str, service: Any, *, replace: bool = False) -> None:
        if capability in self._services and not replace:
            raise ValueError(f"capability already provided: {capability}")
        self._services[capability] = service

    def resolve(self, capability: str) -> Any:
        if capability not in self._services:
            raise KeyError(f"missing capability: {capability}")
        return self._services[capability]

    def optional(self, capability: str, default: Any = None) -> Any:
        return self._services.get(capability, default)

    async def emit(self, event_type: str, payload: Mapping[str, Any]) -> None:
        await self._emit(event_type=event_type, payload=dict(payload))


class HarnessPlugin(ABC):
    """Minimal plugin contract inspired by DeepSeek Harness composition ideas.

    Plugins are application capabilities, not fund-authority. Production execution
    still passes through the deterministic risk gate outside the LLM/provider layer.
    """

    def __init__(self, manifest: PluginManifest) -> None:
        self.manifest = manifest

    async def load(self, context: PluginContext) -> None:
        return None

    async def start(self, context: PluginContext) -> None:
        return None

    async def stop(self, context: PluginContext) -> None:
        return None

    async def unload(self, context: PluginContext) -> None:
        return None
