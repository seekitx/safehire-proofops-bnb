from __future__ import annotations

import unittest

from proofops.domain.errors import PluginDependencyError, PluginLifecycleError
from proofops.harness.contracts import HarnessPlugin, PluginContext, PluginManifest, PluginState
from proofops.harness.registry import PluginRegistry


class ProviderPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        context.provide("test.value", 42)


class ConsumerPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        context.provide("test.answer", context.resolve("test.value") + 1)


class FailingPlugin(HarnessPlugin):
    async def start(self, context: PluginContext) -> None:
        raise RuntimeError("boom")


class PluginHarnessTests(unittest.IsolatedAsyncioTestCase):
    async def test_dependency_order_and_resolution(self) -> None:
        manifests = [
            PluginManifest(
                "consumer",
                "1",
                "tests.test_harness:ConsumerPlugin",
                ("test.answer",),
                ("test.value",),
            ),
            PluginManifest("provider", "1", "tests.test_harness:ProviderPlugin", ("test.value",)),
        ]
        registry = PluginRegistry(manifests)
        await registry.start_all()
        self.assertEqual(registry.resolve("test.answer"), 43)
        states = {item["plugin_id"]: item["state"] for item in registry.list_plugins()}
        self.assertEqual(states["provider"], PluginState.STARTED.value)
        await registry.stop_all()

    async def test_missing_dependency_fails_closed(self) -> None:
        registry = PluginRegistry(
            [
                PluginManifest(
                    "consumer",
                    "1",
                    "tests.test_harness:ConsumerPlugin",
                    ("test.answer",),
                    ("missing",),
                )
            ]
        )
        with self.assertRaises(PluginDependencyError):
            await registry.start_all()

    async def test_duplicate_capability_is_rejected(self) -> None:
        manifests = [
            PluginManifest("one", "1", "tests.test_harness:ProviderPlugin", ("test.value",)),
            PluginManifest("two", "1", "tests.test_harness:ProviderPlugin", ("test.value",)),
        ]
        with self.assertRaises(PluginDependencyError):
            await PluginRegistry(manifests).start_all()

    async def test_start_failure_rolls_back_started_plugins(self) -> None:
        manifests = [
            PluginManifest("provider", "1", "tests.test_harness:ProviderPlugin", ("test.value",)),
            PluginManifest("failure", "1", "tests.test_harness:FailingPlugin", (), ("test.value",)),
        ]
        registry = PluginRegistry(manifests)
        with self.assertRaises(PluginLifecycleError):
            await registry.start_all()
        states = {item["plugin_id"]: item["state"] for item in registry.list_plugins()}
        self.assertIn(states["provider"], {PluginState.UNLOADED.value, PluginState.STOPPED.value})
