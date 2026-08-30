from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import PluginManifest


def load_plugin_manifests(path: str | Path) -> list[PluginManifest]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if raw.get("schema_version") != "1.0":
        raise ValueError("unsupported plugin config schema")
    return [PluginManifest.from_dict(item) for item in raw.get("plugins", [])]


def merge_plugin_overrides(
    manifests: list[PluginManifest], overrides: dict[str, dict[str, Any]]
) -> list[PluginManifest]:
    result: list[PluginManifest] = []
    for manifest in manifests:
        override = overrides.get(manifest.plugin_id, {})
        data = {
            "plugin_id": manifest.plugin_id,
            "version": manifest.version,
            "entrypoint": manifest.entrypoint,
            "provides": manifest.provides,
            "requires": manifest.requires,
            "optional_requires": manifest.optional_requires,
            "config": {**manifest.config, **override.get("config", {})},
            "enabled": override.get("enabled", manifest.enabled),
            "critical": override.get("critical", manifest.critical),
        }
        result.append(PluginManifest.from_dict(data))
    return result
