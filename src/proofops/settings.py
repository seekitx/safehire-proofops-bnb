from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    return default if value is None else value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str = field(default_factory=lambda: os.getenv("APP_ENV", "development"))
    data_dir: Path = field(default_factory=lambda: Path(os.getenv("DATA_DIR", ".data")))
    sqlite_path: Path = field(
        default_factory=lambda: Path(os.getenv("SQLITE_PATH", ".data/safehire.db"))
    )
    evidence_ledger_path: Path = field(
        default_factory=lambda: Path(os.getenv("EVIDENCE_LEDGER_PATH", ".data/evidence.jsonl"))
    )
    plugin_config: Path = field(
        default_factory=lambda: Path(os.getenv("PLUGIN_CONFIG", "config/plugins.json"))
    )
    agent_config: Path = field(
        default_factory=lambda: Path(os.getenv("AGENT_CONFIG", "config/agents.json"))
    )
    execution_mode: str = field(default_factory=lambda: os.getenv("EXECUTION_MODE", "demo"))
    execution_adapter: str = field(default_factory=lambda: os.getenv("EXECUTION_ADAPTER", "demo"))
    allow_onchain_execution: bool = field(
        default_factory=lambda: _bool("ALLOW_ONCHAIN_EXECUTION", False)
    )
    allow_bsc_mainnet: bool = field(default_factory=lambda: _bool("ALLOW_BSC_MAINNET", False))
    admin_api_key: str = field(
        default_factory=lambda: os.getenv("ADMIN_API_KEY", "change-me-before-deploy")
    )
    public_base_url: str = field(
        default_factory=lambda: os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")
    )
    github_repo_url: str = field(default_factory=lambda: os.getenv("GITHUB_REPO_URL", ""))
    bsc_testnet_rpc_url: str = field(
        default_factory=lambda: os.getenv(
            "BSC_TESTNET_RPC_URL", "https://data-seed-prebsc-1-s1.bnbchain.org:8545"
        )
    )
    bsc_mainnet_rpc_url: str = field(
        default_factory=lambda: os.getenv(
            "BSC_MAINNET_RPC_URL", "https://bsc-dataseed.bnbchain.org"
        )
    )
    official_source_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("OFFICIAL_SOURCE_TIMEOUT_SECONDS", "10"))
    )
    scan8004_api_key: str = field(default_factory=lambda: os.getenv("SCAN8004_API_KEY", ""))
    the_graph_api_key: str = field(default_factory=lambda: os.getenv("THE_GRAPH_API_KEY", ""))
    pancake_v3_subgraph_id: str = field(
        default_factory=lambda: os.getenv(
            "PANCAKE_V3_SUBGRAPH_ID",
            "Hv1GncLY5docZoGtXjo4kwbTvxm3MAhVZqBZE4sUT9eZ",
        )
    )
    remote_agent_auth_token: str = field(
        default_factory=lambda: os.getenv("REMOTE_AGENT_AUTH_TOKEN", "")
    )
    remote_agent_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("REMOTE_AGENT_TIMEOUT_SECONDS", "30"))
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            item.strip()
            for item in os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:8000").split(",")
            if item.strip()
        )
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.evidence_ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def validate_runtime(self) -> None:
        if self.app_env != "production":
            return
        if self.admin_api_key in {"", "change-me-before-deploy"}:
            raise ValueError("ADMIN_API_KEY must be changed in production")
        if not self.public_base_url.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL must use HTTPS in production")
        if self.execution_mode != "demo" and not self.allow_onchain_execution:
            raise ValueError(
                "ALLOW_ONCHAIN_EXECUTION must be true when production execution is enabled"
            )
        if self.official_source_timeout_seconds <= 0:
            raise ValueError("OFFICIAL_SOURCE_TIMEOUT_SECONDS must be positive")
