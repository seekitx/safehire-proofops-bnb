from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from proofops.domain.category_metrics import missing_category_metrics
from proofops.domain.models import AgentCategory, DataSource, EvidenceLevel
from proofops.settings import Settings

TX_HASH = re.compile(r"^0x[a-fA-F0-9]{64}$")
ADDRESS = re.compile(r"^0x[a-fA-F0-9]{40}$")
JUDGING_END = datetime(2026, 9, 23, 23, 59, 59, tzinfo=timezone.utc)


@dataclass(frozen=True)
class GateCheck:
    check_id: str
    passed: bool
    severity: str
    message: str
    remediation: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def _public_https(url: str) -> bool:
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    host = (parsed.hostname or "").lower()
    return (
        parsed.scheme == "https"
        and bool(host)
        and host not in {"localhost", "127.0.0.1", "0.0.0.0"}
        and not host.endswith(".local")
    )


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


class SubmissionValidator:
    """Fail-closed contest readiness validator.

    Local completeness and real-world evidence are separate. This gate verifies the
    shape and honesty labels of saved evidence, but BscScan/official platform links
    still need final human review before submission.
    """

    def __init__(
        self,
        *,
        registry: Any,
        scorer: Any,
        ledger: Any,
        project_root: Path,
        settings: Settings,
    ) -> None:
        self._registry = registry
        self._scorer = scorer
        self._ledger = ledger
        self._root = project_root
        self._settings = settings

    def _check_public_delivery(self) -> list[GateCheck]:
        site_ok = _public_https(self._settings.public_base_url)
        repo_ok = (
            _public_https(self._settings.github_repo_url)
            and (urlparse(self._settings.github_repo_url).hostname or "").lower() == "github.com"
        )
        return [
            GateCheck(
                "public_https_site",
                site_ok,
                "P0",
                "Public HTTPS judging URL configured"
                if site_ok
                else "PUBLIC_BASE_URL is local, empty, or not HTTPS",
                "Deploy the app publicly over HTTPS and set PUBLIC_BASE_URL.",
            ),
            GateCheck(
                "public_github_repository",
                repo_ok,
                "P0",
                "Public GitHub repository URL configured"
                if repo_ok
                else "GITHUB_REPO_URL is missing or not a public GitHub HTTPS URL",
                "Publish the repository and set GITHUB_REPO_URL to its HTTPS address.",
            ),
        ]

    def _check_agents(self) -> list[GateCheck]:
        checks: list[GateCheck] = []
        agents = self._registry.list()
        categories = {agent.category for agent in agents}
        checks.append(
            GateCheck(
                "four_categories",
                categories == set(AgentCategory),
                "P0",
                f"Found categories: {sorted(item.value for item in categories)}",
                "Provide at least one callable agent in each required category.",
            )
        )
        for agent in agents:
            demo_only = "demo" in agent.tags
            missing = missing_category_metrics(agent.category, dict(agent.metrics.category_metrics))
            checks.append(
                GateCheck(
                    f"metrics:{agent.agent_id}",
                    not missing,
                    "P0",
                    "Category metrics complete" if not missing else f"Missing: {missing}",
                    "Populate every category-specific metric with source labels.",
                )
            )
            endpoint_ok = _public_https(agent.endpoint)
            checks.append(
                GateCheck(
                    f"public_endpoint:{agent.agent_id}",
                    endpoint_ok,
                    "P2" if demo_only else "P0",
                    "Callable public HTTPS endpoint present"
                    if endpoint_ok
                    else "Agent endpoint is local or does not use HTTPS",
                    "Deploy the callable endpoint and update config/agents.json.",
                )
            )
            live_evidence = [
                item
                for item in agent.evidence
                if item.source in {DataSource.LIVE_ONCHAIN, DataSource.TESTNET_EVIDENCE}
                and item.level >= EvidenceLevel.TESTNET_TRANSACTION
                and item.tx_hash
                and TX_HASH.fullmatch(item.tx_hash)
                and item.chain_id in {56, 97}
            ]
            live_ok = bool(
                agent.live_bsc
                and agent.contract_address
                and ADDRESS.fullmatch(agent.contract_address)
                and live_evidence
            )
            checks.append(
                GateCheck(
                    f"live_bsc:{agent.agent_id}",
                    live_ok,
                    "P2" if demo_only else "P0",
                    "Live BSC contract and transaction evidence present"
                    if live_ok
                    else "Agent is fixture-only or lacks valid BSC contract/transaction evidence",
                    "Deploy/register the Agent on BSC and save an Explorer-valid transaction hash.",
                )
            )
            fixture_only = bool(agent.evidence) and all(
                item.source == DataSource.DEMO_FIXTURE for item in agent.evidence
            )
            checks.append(
                GateCheck(
                    f"fixture_not_live:{agent.agent_id}",
                    not (agent.live_bsc and fixture_only),
                    "P0",
                    "Fixture labeling is consistent",
                    "Never mark a fixture-only agent as live_bsc=true.",
                )
            )
        return checks

    def _check_live_market_catalog(self) -> GateCheck:
        catalog = _read_json(
            self._root / "evidence" / "marketplace" / "live-agent-catalog.json"
        )
        agents = catalog.get("agents") if catalog else None
        observed_at = None
        if catalog and catalog.get("observed_at"):
            try:
                observed_at = datetime.fromisoformat(
                    str(catalog["observed_at"]).replace("Z", "+00:00")
                )
            except ValueError:
                observed_at = None
        categories = {
            str(item.get("category"))
            for item in agents or []
            if isinstance(item, dict)
        }
        required_categories = {item.value for item in AgentCategory}
        records_valid = bool(
            isinstance(agents, list)
            and len(agents) >= 4
            and all(
                isinstance(item, dict)
                and int(item.get("token_id", 0)) > 0
                and TX_HASH.fullmatch(str(item.get("created_tx_hash", "")))
                and _public_https(str(item.get("registration_url", "")))
                and _public_https(str(item.get("registry_url", "")))
                and str(item.get("skill_id", "")).strip()
                and isinstance(item.get("required_inputs"), dict)
                for item in agents
            )
        )
        now = datetime.now(timezone.utc)
        fresh = bool(
            observed_at
            and observed_at <= now
            and (now - observed_at).total_seconds() <= 48 * 60 * 60
        )
        ready = bool(
            catalog
            and catalog.get("evidence_mode") == "live"
            and catalog.get("chain_id") == 56
            and catalog.get("operator_external") is True
            and catalog.get("a2a_list_verified") is True
            and _public_https(str(catalog.get("agent_card_url", "")))
            and _public_https(str(catalog.get("a2a_endpoint", "")))
            and categories == required_categories
            and records_valid
            and fresh
        )
        return GateCheck(
            "live_bsc_market_catalog",
            ready,
            "P0",
            "Four current BSC mainnet Agent registrations cover every required category"
            if ready
            else "Live BSC Agent catalog is missing, stale, malformed, or incomplete",
            "Refresh the public ERC-8004/A2A snapshot within 48 hours and preserve all four registration links.",
        )

    def _check_required_files(self) -> GateCheck:
        required = [
            "README.md",
            "docs/00_OFFICIAL_IMPLEMENTATION_REFERENCES.md",
            "docs/01_COMPETITION_REQUIREMENTS.md",
            "docs/02_ARCHITECTURE.md",
            "docs/03_DOMAIN_AND_MODULE_DESIGN.md",
            "docs/04_PLUGIN_DECOUPLING.md",
            "docs/05_MULTI_AGENT_ADVERSARIAL_REVIEW.md",
            "docs/06_SECURITY_AND_THREAT_MODEL.md",
            "docs/07_CONSTRUCTION_BLUEPRINT.md",
            "docs/08_DEMO_AND_SUBMISSION.md",
            "docs/09_OPERATIONS.md",
            "docs/10_EXTERNAL_COMPLETION_CHECKLIST.md",
            "contracts/src/AgentRegistry.sol",
            "contracts/src/ScopedExecutionPolicy.sol",
            "contracts/src/EvidenceAnchor.sol",
            "agent-studio/safehireagents/app/agent/studio.toml",
            "agent-studio/safehireagents/app/agent/src/tools.ts",
            "agent-studio/safehireagents/app/agent/src/proofopsPrompt.ts",
            "agent-studio/safehireagents/pnpm-lock.yaml",
        ]
        missing = [item for item in required if not (self._root / item).is_file()]
        return GateCheck(
            "required_artifacts",
            not missing,
            "P0",
            "All design and submission artifacts exist" if not missing else f"Missing: {missing}",
            "Restore every listed design, security, operations and submission artifact.",
        )

    def _check_termix(self) -> GateCheck:
        path = self._root / "evidence" / "termix" / "agent-advantage-report.json"
        report = _read_json(path)
        tasks = report.get("tasks") if report else None
        categories = set(report.get("categories", [])) if report else set()
        valid_hashes = False
        if isinstance(tasks, list) and tasks:
            valid_hashes = all(
                isinstance(task, dict)
                and isinstance(task.get("agent"), dict)
                and isinstance(task.get("manual"), dict)
                and re.fullmatch(r"[a-f0-9]{64}", str(task["agent"].get("output_sha256", "")))
                and re.fullmatch(r"[a-f0-9]{64}", str(task["manual"].get("output_sha256", "")))
                for task in tasks
            )
        ready = bool(
            report
            and report.get("evidence_mode") == "live"
            and isinstance(tasks, list)
            and len(tasks) >= 3
            and valid_hashes
            and categories.intersection({"rebalancing", "grid_trading", "health_factor_monitoring"})
        )
        return GateCheck(
            "termix_live_advantage_report",
            ready,
            "P1",
            "Live TermiX report with raw-output hashes is present"
            if ready
            else "Live TermiX report is missing, fixture-only, or has fewer than three valid tasks",
            "Run real same-prompt agent/manual tasks and build the strict TermiX report.",
        )

    def _check_long_lived_runtime(self) -> GateCheck:
        record = _read_json(
            self._root / "evidence" / "sponsor-integration" / "agent-studio-deployment.json"
        )
        expires_at = None
        if record and record.get("expires_at"):
            try:
                expires_at = datetime.fromisoformat(str(record["expires_at"]).replace("Z", "+00:00"))
            except ValueError:
                expires_at = None
        environment = str(record.get("environment", "")) if record else ""
        durable_without_expiry = bool(record and not record.get("expires_at") and environment != "trial")
        ready = bool(
            record
            and record.get("evidence_mode") == "live"
            and record.get("status") == "running"
            and _public_https(str(record.get("endpoint", "")))
            and (durable_without_expiry or (expires_at and expires_at >= JUDGING_END))
        )
        return GateCheck(
            "long_lived_agent_runtime",
            ready,
            "P0",
            "Public Agent runtime is recorded through the judging period"
            if ready
            else "Current Agent runtime is missing, temporary, or expires before judging ends",
            "Deploy the Agent to durable hosting and record its public endpoint without a trial expiry.",
        )

    def _check_erc8183_hire(self) -> GateCheck:
        record = _read_json(
            self._root / "evidence" / "sponsor-integration" / "erc8183-job-808.json"
        )
        transactions = record.get("transactions") if record else None
        expected_steps = {
            "create_job",
            "register_job",
            "set_budget",
            "approve_u",
            "fund_job",
            "submit_delivery",
            "settle_job",
        }
        steps = {
            str(item.get("step"))
            for item in transactions or []
            if isinstance(item, dict)
            and item.get("receipt_status") == 1
            and TX_HASH.fullmatch(str(item.get("tx_hash", "")))
        }
        verification = record.get("verification", {}) if record else {}
        ready = bool(
            record
            and record.get("evidence_mode") == "live"
            and record.get("chain_id") == 97
            and int(record.get("job_id", 0)) > 0
            and expected_steps.issubset(steps)
            and verification.get("completed") is True
            and verification.get("provider_payment_transfer_observed") is True
            and str(record.get("payment", {}).get("budget_u")) == "0.1"
        )
        return GateCheck(
            "erc8183_completed_hire",
            ready,
            "P1",
            "Completed ERC-8183 0.1 U hire evidence is present"
            if ready
            else "Completed ERC-8183 hire evidence is missing or incomplete",
            "Preserve create, fund, submit and settle receipts plus the final provider payment proof.",
        )

    def _check_pancakeswap_benefit(self) -> GateCheck:
        report = _read_json(
            self._root / "evidence" / "pancakeswap" / "live-benefit-report.json"
        )
        ready = bool(
            report
            and report.get("evidence_mode") == "live"
            and report.get("beneficiary") in {"trader", "liquidity_provider"}
            and isinstance(report.get("observed_block"), int)
            and report.get("observed_block", 0) > 0
            and _public_https(str(report.get("source_url", "")))
            and str(report.get("measurable_benefit", "")).strip()
            and str(report.get("risk_boundary", "")).strip()
        )
        return GateCheck(
            "pancakeswap_live_benefit",
            ready,
            "P1",
            "Live PancakeSwap user-benefit report is present"
            if ready
            else "PancakeSwap benefit is not yet backed by a live pool or position observation",
            "Use real PancakeSwap data at a recorded block and explain the measurable benefit and risk limit.",
        )

    def _check_contract_deployment(self) -> GateCheck:
        manifest = _read_json(self._root / "deployments" / "bsc-testnet.json")
        contracts = manifest.get("contracts") if manifest else None
        required_names = {
            "AgentRegistry",
            "ScopedExecutionPolicy",
            "EvidenceAnchor",
        }
        valid = bool(
            manifest
            and manifest.get("chain_id") == 97
            and isinstance(contracts, dict)
            and required_names.issubset(contracts)
            and all(
                isinstance(contracts[name], dict)
                and ADDRESS.fullmatch(str(contracts[name].get("address", "")))
                and TX_HASH.fullmatch(str(contracts[name].get("deployment_tx_hash", "")))
                for name in required_names
            )
        )
        return GateCheck(
            "bsc_testnet_contract_deployment",
            valid,
            "P0",
            "All three contracts have BSC Testnet addresses and deployment transactions"
            if valid
            else "BSC Testnet deployment manifest is missing or incomplete",
            "Deploy with the contract script, verify on BscScan, and save deployments/bsc-testnet.json.",
        )

    def _check_transactions(self) -> GateCheck:
        tx_dir = self._root / "evidence" / "tx"
        valid_records = 0
        for path in tx_dir.glob("*.json") if tx_dir.exists() else []:
            record = _read_json(path)
            if not record or record.get("evidence_mode") != "live":
                continue
            if (
                record.get("chain_id") in {56, 97}
                and TX_HASH.fullmatch(str(record.get("tx_hash", "")))
                and _public_https(str(record.get("explorer_url", "")))
                and record.get("successful") is True
                and record.get("source") in {"live_onchain", "testnet_evidence"}
            ):
                valid_records += 1
        return GateCheck(
            "real_bsc_transaction",
            valid_records > 0,
            "P0",
            f"Found {valid_records} structurally valid live BSC transaction records",
            "Execute a bounded BSC action, verify its receipt, and capture it with scripts/capture_bsc_evidence.py.",
        )

    def _check_agent_registration(self) -> GateCheck:
        record = _read_json(
            self._root / "evidence" / "sponsor-integration" / "erc8004-registration.json"
        )
        ready = bool(
            record
            and record.get("chain_id") == 97
            and str(record.get("agent_id", ""))
            and ADDRESS.fullmatch(str(record.get("registry_address", "")))
            and ADDRESS.fullmatch(str(record.get("owner", "")))
            and TX_HASH.fullmatch(str(record.get("tx_hash", "")))
            and _public_https(str(record.get("endpoint", "")))
        )
        return GateCheck(
            "erc8004_registration",
            ready,
            "P0",
            "ERC-8004 BSC Testnet registration evidence present"
            if ready
            else "ERC-8004 registration evidence is missing or incomplete",
            "Register the deployed public Agent, resolve it, and save registry/owner/agent id/transaction evidence.",
        )

    def _check_submission_metadata(self) -> GateCheck:
        metadata = _read_json(self._root / "submission" / "submission.json")
        ready = bool(
            metadata
            and _public_https(str(metadata.get("project_url", "")))
            and _public_https(str(metadata.get("github_url", "")))
            and str(metadata.get("title", "")).strip()
            and str(metadata.get("one_liner", "")).strip()
        )
        return GateCheck(
            "submission_metadata",
            ready,
            "P0",
            "Required project and repository submission metadata present"
            if ready
            else "Submission metadata or required public links are missing",
            "Complete submission/submission.json only with public URLs that judges can open.",
        )

    def _check_optional_demo_video(self) -> GateCheck:
        metadata = _read_json(self._root / "submission" / "submission.json")
        url = str(metadata.get("demo_video_url", "")).strip() if metadata else ""
        seconds = metadata.get("demo_video_seconds") if metadata else None
        ready = bool(
            url
            and _public_https(url)
            and isinstance(seconds, (int, float))
            and 0 < float(seconds) <= 300
        )
        return GateCheck(
            "optional_demo_video",
            ready,
            "P2",
            "Optional public demo video is under five minutes"
            if ready
            else "Optional demo video is not provided or is longer than five minutes",
            "Add a concise public demo only if it improves judge comprehension; it is not a current form requirement.",
        )

    def run(self) -> dict[str, Any]:
        checks = [
            *self._check_public_delivery(),
            *self._check_agents(),
            self._check_live_market_catalog(),
            self._check_required_files(),
        ]
        ledger_result = self._ledger.verify()
        checks.append(
            GateCheck(
                "evidence_ledger_integrity",
                bool(ledger_result["valid"]),
                "P0",
                f"Ledger records={ledger_result['records']} head={ledger_result['head_hash']}",
                "Restore from a valid export; never edit JSONL records in place.",
            )
        )
        checks.extend(
            [
                self._check_termix(),
                self._check_long_lived_runtime(),
                self._check_contract_deployment(),
                self._check_transactions(),
                self._check_agent_registration(),
                self._check_erc8183_hire(),
                self._check_pancakeswap_benefit(),
                self._check_submission_metadata(),
                self._check_optional_demo_video(),
            ]
        )
        blockers = [check for check in checks if check.severity == "P0" and not check.passed]
        partner_gaps = [check for check in checks if check.severity == "P1" and not check.passed]
        return {
            "ready": not blockers,
            "summary": {
                "total": len(checks),
                "passed": sum(check.passed for check in checks),
                "failed": sum(not check.passed for check in checks),
                "p0_blockers": len(blockers),
            },
            "blockers": [check.to_dict() for check in blockers],
            "partner_prize_gaps": [check.to_dict() for check in partner_gaps],
            "checks": [check.to_dict() for check in checks],
            "honesty_boundary": (
                "The gate validates saved evidence structure. Final URLs, BscScan receipts, platform state and prize eligibility still require live review."
            ),
        }
