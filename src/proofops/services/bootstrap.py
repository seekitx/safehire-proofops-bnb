from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from proofops.agents import AgentInvocationService
from proofops.execution.adapters import (
    DemoExecutionAdapter,
    DisabledOnchainAdapter,
    ExecutionAdapter,
    RemoteAgentExecutionAdapter,
)
from proofops.execution.risk_gate import RiskGate
from proofops.execution.service import TaskService
from proofops.execution.store import SQLiteStore
from proofops.harness.config import load_plugin_manifests
from proofops.harness.contracts import PluginManifest
from proofops.harness.registry import PluginRegistry
from proofops.harness.trace import TraceSubscriber
from proofops.integrations import BscNetworkService, OfficialSourceClient
from proofops.services.marketplace import MarketplaceService
from proofops.services.submission import SubmissionValidator
from proofops.services.wallet_auth import WalletAuthService
from proofops.settings import Settings


@dataclass
class Application:
    settings: Settings
    harness: PluginRegistry
    marketplace: MarketplaceService
    agents: AgentInvocationService
    network: BscNetworkService
    official_sources: OfficialSourceClient
    wallet_auth: WalletAuthService
    tasks: TaskService
    submission: SubmissionValidator

    async def close(self) -> None:
        await self.harness.stop_all()


async def build_application(settings: Settings | None = None) -> Application:
    settings = settings or Settings()
    settings.ensure_dirs()
    settings.validate_runtime()

    # Ensure plugin config receives the resolved ledger path without mutating source files.
    manifests = load_plugin_manifests(settings.plugin_config)
    patched = []
    for manifest in manifests:
        if manifest.plugin_id == "evidence-ledger":
            data = {
                "plugin_id": manifest.plugin_id,
                "version": manifest.version,
                "entrypoint": manifest.entrypoint,
                "provides": manifest.provides,
                "requires": manifest.requires,
                "optional_requires": manifest.optional_requires,
                "config": {**manifest.config, "path": str(settings.evidence_ledger_path)},
                "enabled": manifest.enabled,
                "critical": manifest.critical,
            }
            manifest = PluginManifest.from_dict(data)
        elif manifest.plugin_id == "agent-registry":
            data = {
                "plugin_id": manifest.plugin_id,
                "version": manifest.version,
                "entrypoint": manifest.entrypoint,
                "provides": manifest.provides,
                "requires": manifest.requires,
                "optional_requires": manifest.optional_requires,
                "config": {
                    **manifest.config,
                    "path": str(settings.agent_config),
                    "public_base_url": settings.public_base_url,
                },
                "enabled": manifest.enabled,
                "critical": manifest.critical,
            }
            manifest = PluginManifest.from_dict(data)
        patched.append(manifest)

    harness = PluginRegistry(patched)
    await harness.start_all()
    ledger = harness.resolve("evidence.ledger")
    harness.event_bus.subscribe("*", TraceSubscriber(ledger))

    store = SQLiteStore(settings.sqlite_path)
    registry = harness.resolve("agents.registry")
    adapter: ExecutionAdapter = DemoExecutionAdapter()
    if settings.execution_mode != "demo":
        if not settings.allow_onchain_execution:
            adapter = DisabledOnchainAdapter(
                "Onchain execution requested but ALLOW_ONCHAIN_EXECUTION=false"
            )
        elif settings.execution_adapter == "remote_agent":
            adapter = RemoteAgentExecutionAdapter(
                endpoint_resolver=lambda agent_id: str(registry.get(agent_id).endpoint),
                auth_token=settings.remote_agent_auth_token,
                timeout_seconds=settings.remote_agent_timeout_seconds,
            )
        else:
            adapter = DisabledOnchainAdapter(
                "Set EXECUTION_ADAPTER=remote_agent for deployed Agent Studio endpoints"
            )
    gate = RiskGate(
        allow_bsc_mainnet=settings.allow_bsc_mainnet,
        kill_switch=lambda: store.get_flag("kill_switch", "false") == "true",
        spent_today=store.spent_today,
        # Creation idempotency keys are separate from execution idempotency in a deployed adapter.
        idempotency_seen=lambda _key: False,
    )
    tasks = TaskService(store=store, ledger=ledger, risk_gate=gate, adapter=adapter)
    wallet_auth = WalletAuthService(store)
    marketplace = MarketplaceService(registry=registry, scorer=harness.resolve("agents.proof"))
    agents = AgentInvocationService(registry=registry, ledger=ledger)
    network = BscNetworkService(
        testnet_rpc_url=settings.bsc_testnet_rpc_url,
        mainnet_rpc_url=settings.bsc_mainnet_rpc_url,
    )
    official_sources = OfficialSourceClient(
        timeout_seconds=settings.official_source_timeout_seconds,
        scan8004_api_key=settings.scan8004_api_key,
        the_graph_api_key=settings.the_graph_api_key,
        pancake_v3_subgraph_id=settings.pancake_v3_subgraph_id,
    )
    submission = SubmissionValidator(
        registry=harness.resolve("agents.registry"),
        scorer=harness.resolve("agents.proof"),
        ledger=ledger,
        project_root=Path.cwd(),
        settings=settings,
    )
    return Application(
        settings,
        harness,
        marketplace,
        agents,
        network,
        official_sources,
        wallet_auth,
        tasks,
        submission,
    )
