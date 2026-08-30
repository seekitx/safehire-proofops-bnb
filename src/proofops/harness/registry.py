from __future__ import annotations

import importlib
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from proofops.domain.errors import PluginDependencyError, PluginLifecycleError

from .contracts import HarnessPlugin, PluginContext, PluginManifest, PluginState
from .event_bus import EventBus


@dataclass
class PluginHandle:
    manifest: PluginManifest
    instance: HarnessPlugin | None = None
    state: PluginState = PluginState.DISCOVERED
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.manifest.plugin_id,
            "version": self.manifest.version,
            "provides": list(self.manifest.provides),
            "requires": list(self.manifest.requires),
            "enabled": self.manifest.enabled,
            "critical": self.manifest.critical,
            "state": self.state.value,
            "error": self.error,
        }


class PluginRegistry:
    def __init__(self, manifests: Iterable[PluginManifest], services: dict[str, Any] | None = None):
        items = list(manifests)
        if len({item.plugin_id for item in items}) != len(items):
            raise ValueError("duplicate plugin_id")
        self._handles = {item.plugin_id: PluginHandle(item) for item in items}
        self._services: dict[str, Any] = services or {}
        self._bus = EventBus()
        self._ctx = PluginContext(self._services, self._bus.emit)
        self._started_order: list[str] = []

    @property
    def event_bus(self) -> EventBus:
        return self._bus

    @property
    def services(self) -> dict[str, Any]:
        return self._services

    def resolve(self, capability: str) -> Any:
        return self._ctx.resolve(capability)

    def list_plugins(self) -> list[dict[str, Any]]:
        return [handle.to_dict() for handle in self._handles.values()]

    def _ordered_ids(self) -> list[str]:
        enabled = {
            plugin_id: handle.manifest
            for plugin_id, handle in self._handles.items()
            if handle.manifest.enabled
        }
        capability_owner: dict[str, str] = {}
        for plugin_id, manifest in enabled.items():
            for capability in manifest.provides:
                if capability in capability_owner:
                    raise PluginDependencyError(
                        f"capability {capability} provided by both "
                        f"{capability_owner[capability]} and {plugin_id}"
                    )
                capability_owner[capability] = plugin_id

        deps: dict[str, set[str]] = {plugin_id: set() for plugin_id in enabled}
        for plugin_id, manifest in enabled.items():
            for capability in manifest.requires:
                if capability in self._services:
                    continue
                owner = capability_owner.get(capability)
                if owner is None:
                    raise PluginDependencyError(
                        f"{plugin_id} requires missing capability {capability}"
                    )
                deps[plugin_id].add(owner)

        ordered: list[str] = []
        ready = sorted(plugin_id for plugin_id, values in deps.items() if not values)
        while ready:
            current = ready.pop(0)
            ordered.append(current)
            for plugin_id in sorted(deps):
                if current in deps[plugin_id]:
                    deps[plugin_id].remove(current)
                    if not deps[plugin_id] and plugin_id not in ordered and plugin_id not in ready:
                        ready.append(plugin_id)
                        ready.sort()
        if len(ordered) != len(enabled):
            unresolved = [plugin_id for plugin_id, values in deps.items() if values]
            raise PluginDependencyError(f"plugin dependency cycle: {unresolved}")
        return ordered

    @staticmethod
    def _instantiate(manifest: PluginManifest) -> HarnessPlugin:
        module_name, separator, class_name = manifest.entrypoint.partition(":")
        if not separator:
            raise PluginLifecycleError(
                f"invalid entrypoint {manifest.entrypoint!r}; expected module:Class"
            )
        module = importlib.import_module(module_name)
        plugin_class = getattr(module, class_name)
        instance = plugin_class(manifest)
        if not isinstance(instance, HarnessPlugin):
            raise PluginLifecycleError(f"{manifest.entrypoint} is not a HarnessPlugin")
        return instance

    async def start_all(self) -> None:
        await self._bus.emit("harness.starting", {"plugin_count": len(self._handles)})
        try:
            for plugin_id in self._ordered_ids():
                handle = self._handles[plugin_id]
                try:
                    handle.instance = self._instantiate(handle.manifest)
                    await handle.instance.load(self._ctx)
                    handle.state = PluginState.LOADED
                    await self._bus.emit("plugin.loaded", {"plugin_id": plugin_id})
                    await handle.instance.start(self._ctx)
                    handle.state = PluginState.STARTED
                    self._started_order.append(plugin_id)
                    await self._bus.emit("plugin.started", {"plugin_id": plugin_id})
                except Exception as exc:
                    handle.state = PluginState.FAILED
                    handle.error = str(exc)
                    await self._bus.emit(
                        "plugin.failed", {"plugin_id": plugin_id, "error": str(exc)}
                    )
                    raise PluginLifecycleError(f"failed to start {plugin_id}: {exc}") from exc
        except Exception:
            await self.stop_all(reason="startup_rollback")
            raise
        await self._bus.emit("harness.started", {"plugins": list(self._started_order)})

    async def stop_plugin(self, plugin_id: str, *, reason: str = "manual") -> None:
        handle = self._handles[plugin_id]
        if handle.instance is None or handle.state != PluginState.STARTED:
            return
        await handle.instance.stop(self._ctx)
        handle.state = PluginState.STOPPED
        await self._bus.emit("plugin.stopped", {"plugin_id": plugin_id, "reason": reason})
        await handle.instance.unload(self._ctx)
        handle.state = PluginState.UNLOADED
        await self._bus.emit("plugin.unloaded", {"plugin_id": plugin_id})
        if plugin_id in self._started_order:
            self._started_order.remove(plugin_id)
        for capability in handle.manifest.provides:
            self._services.pop(capability, None)

    async def stop_all(self, *, reason: str = "shutdown") -> None:
        for plugin_id in reversed(list(self._started_order)):
            try:
                await self.stop_plugin(plugin_id, reason=reason)
            # Shutdown is best-effort across independently implemented plugins.
            except Exception as exc:  # noqa: BLE001
                handle = self._handles[plugin_id]
                handle.state = PluginState.FAILED
                handle.error = str(exc)
        await self._bus.emit("harness.stopped", {"reason": reason})

    async def restart_plugin(self, plugin_id: str) -> None:
        handle = self._handles[plugin_id]
        dependants = [
            other.manifest.plugin_id
            for other in self._handles.values()
            if any(cap in other.manifest.requires for cap in handle.manifest.provides)
            and other.state == PluginState.STARTED
        ]
        if dependants:
            raise PluginLifecycleError(
                f"cannot restart {plugin_id}; active dependants: {dependants}"
            )
        await self.stop_plugin(plugin_id, reason="restart")
        handle.instance = self._instantiate(handle.manifest)
        await handle.instance.load(self._ctx)
        handle.state = PluginState.LOADED
        await handle.instance.start(self._ctx)
        handle.state = PluginState.STARTED
        self._started_order.append(plugin_id)
