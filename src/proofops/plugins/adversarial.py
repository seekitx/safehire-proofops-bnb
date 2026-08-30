from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from proofops.harness.contracts import HarnessPlugin, PluginContext


class CouncilRole(str, Enum):
    BNB_MAIN_JUDGE = "bnb_main_judge"
    TERMIX_SPONSOR_JUDGE = "termix_sponsor_judge"
    PANCAKE_DEFI_REVIEWER = "pancake_defi_reviewer"
    SECURITY_RED_TEAM = "security_red_team"
    SYSTEM_ARCHITECT = "system_architect"
    SOLO_BUILDER_SCHEDULE_ATTACKER = "solo_builder_schedule_attacker"
    EVIDENCE_AUDITOR = "evidence_auditor"


@dataclass(frozen=True)
class Proposal:
    title: str
    problem: str
    user_path: tuple[str, ...]
    sponsor_integrations: tuple[str, ...]
    architecture: str
    safety_controls: tuple[str, ...]
    evidence_plan: tuple[str, ...]
    estimated_days: float
    uses_generic_chat: bool = False
    deterministic_scoring: bool = True
    live_bsc_plan: bool = True
    fixture_labeling: bool = True

    @classmethod
    def safehire_default(cls) -> Proposal:
        return cls(
            title="SafeHire / ProofOps",
            problem="Users cannot verify which DeFi agent deserves scoped access to their money.",
            user_path=(
                "compare",
                "evidence",
                "simulate",
                "set_limits",
                "hire",
                "receipt",
                "revoke",
            ),
            sponsor_integrations=(
                "BNB Agent Studio / ERC-8183",
                "PancakeSwap",
                "TermiX benchmarks",
            ),
            architecture="modular_monolith_plus_isolated_execution_gateway",
            safety_controls=(
                "deterministic risk gate",
                "allowlist",
                "spend cap",
                "expiry",
                "idempotency",
                "human approval",
                "kill switch",
            ),
            evidence_plan=(
                "tx hash",
                "contract address",
                "raw benchmark outputs",
                "hash-chain ledger",
                "source labels",
                "failure-path screenshots",
            ),
            estimated_days=9.0,
        )


@dataclass(frozen=True)
class Argument:
    role: CouncilRole
    score: int
    verdict: str
    strengths: tuple[str, ...]
    attacks: tuple[str, ...]
    required_changes: tuple[str, ...]
    veto: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["role"] = self.role.value
        data["strengths"] = list(self.strengths)
        data["attacks"] = list(self.attacks)
        data["required_changes"] = list(self.required_changes)
        return data


@dataclass(frozen=True)
class DebateDecision:
    accepted: bool
    average_score: float
    vetoes: tuple[str, ...]
    arguments: tuple[Argument, ...]
    non_negotiables: tuple[str, ...]
    deferred: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "average_score": self.average_score,
            "vetoes": list(self.vetoes),
            "arguments": [item.to_dict() for item in self.arguments],
            "non_negotiables": list(self.non_negotiables),
            "deferred": list(self.deferred),
        }


class AdversarialCouncil:
    """Seven deterministic reviewer agents with optional LLM elaboration.

    The deterministic verdict is authoritative. A language-model provider may
    produce wording or extra questions, but cannot remove a security/evidence veto.
    """

    def __init__(self, ledger: Any, llm_provider: Any | None = None) -> None:
        self._ledger = ledger
        self._llm = llm_provider

    def review(self, proposal: Proposal) -> DebateDecision:
        arguments = tuple(self._review_role(role, proposal) for role in CouncilRole)
        average = round(sum(item.score for item in arguments) / len(arguments), 2)
        vetoes = tuple(item.role.value for item in arguments if item.veto)
        accepted = average >= 78 and not vetoes
        non_negotiables = (
            "One complete product; no second submission for the same team.",
            "Four categories have category-specific metrics and callable endpoints.",
            "AgentProof is deterministic and evidence-capped.",
            "At least one reproducible real BSC transaction before submission.",
            "AI cannot bypass simulation, policy, permission or human approval.",
            "Fixtures are visually and machine-readably labeled.",
            "Three raw manual-vs-agent benchmark reports are included.",
        )
        deferred = (
            "General-purpose AI chat",
            "Multi-chain expansion",
            "Complex microservice split",
            "Mainnet unattended execution",
            "Altana integration if it blocks cash-prize paths for more than half a day",
            "Advanced ML price prediction",
        )
        decision = DebateDecision(
            accepted=accepted,
            average_score=average,
            vetoes=vetoes,
            arguments=arguments,
            non_negotiables=non_negotiables,
            deferred=deferred,
        )
        self._ledger.append(
            kind="adversarial_design_decision",
            source="design.council",
            payload={"proposal": asdict(proposal), "decision": decision.to_dict()},
        )
        return decision

    def _review_role(self, role: CouncilRole, p: Proposal) -> Argument:
        if role == CouncilRole.BNB_MAIN_JUDGE:
            score = 92
            attacks = []
            changes = []
            if len(p.user_path) > 8:
                score -= 12
                attacks.append("Demo path is too long for judging.")
            if p.uses_generic_chat:
                score -= 20
                attacks.append("Generic chat dilutes the marketplace value proposition.")
            if not p.live_bsc_plan:
                score -= 40
                attacks.append("Listed agents are not planned to be live on BSC.")
                changes.append("Deploy agent endpoints and registry evidence on BSC.")
            return Argument(
                role,
                score,
                "Strong BNB-native trust layer",
                (
                    "Clear problem and short path",
                    "Sponsor integrations sit on the critical path",
                ),
                tuple(attacks),
                tuple(changes),
                veto=not p.live_bsc_plan,
            )

        if role == CouncilRole.TERMIX_SPONSOR_JUDGE:
            has_bench = any("TermiX" in item for item in p.sponsor_integrations)
            score = 90 if has_bench else 55
            return Argument(
                role,
                score,
                "Benchmarkable agent advantage",
                (
                    "Time, cost and quality can be measured",
                    "High-risk financial tasks are explicit",
                ),
                (() if has_bench else ("No three-task comparison plan.",)),
                (() if has_bench else ("Add raw manual-vs-agent reports.",)),
                veto=not has_bench,
            )

        if role == CouncilRole.PANCAKE_DEFI_REVIEWER:
            has_pancake = any("Pancake" in item for item in p.sponsor_integrations)
            return Argument(
                role,
                88 if has_pancake else 58,
                "One LP workflow is deeper than many logos",
                (
                    "Explainable range policy",
                    "Cost-aware simulation before execution",
                ),
                (() if has_pancake else ("No protocol-native flagship action.",)),
                (() if has_pancake else ("Make LP Guardian a real Pancake workflow.",)),
                veto=False,
            )

        if role == CouncilRole.SECURITY_RED_TEAM:
            controls = set(p.safety_controls)
            required = {
                "deterministic risk gate",
                "allowlist",
                "spend cap",
                "expiry",
                "idempotency",
                "human approval",
                "kill switch",
            }
            missing = sorted(required - controls)
            score = 95 - len(missing) * 12
            return Argument(
                role,
                score,
                "Fail closed with independent execution authority",
                (
                    "LLM is advisory",
                    "Revocation and idempotency are explicit",
                ),
                tuple(f"Missing control: {item}" for item in missing),
                tuple(f"Implement {item}" for item in missing),
                veto=bool(missing),
            )

        if role == CouncilRole.SYSTEM_ARCHITECT:
            modular = "modular_monolith" in p.architecture
            score = 91 if modular else 68
            attacks_tuple: tuple[str, ...] = (
                () if modular else ("Service split increases failure modes and deployment burden.",)
            )
            changes_tuple: tuple[str, ...] = (
                () if modular else ("Use a modular monolith and isolate only execution/signing.",)
            )
            return Argument(
                role,
                score,
                "Bounded plugin architecture",
                (
                    "Capabilities are replaceable",
                    "Execution boundary remains deterministic",
                ),
                attacks_tuple,
                changes_tuple,
            )

        if role == CouncilRole.SOLO_BUILDER_SCHEDULE_ATTACKER:
            score = 92 if p.estimated_days <= 10 else max(40, int(100 - p.estimated_days * 4))
            schedule_attacks: tuple[str, ...] = (
                () if p.estimated_days <= 10 else ("Plan exceeds solo-builder contest window.",)
            )
            schedule_changes: tuple[str, ...] = (
                () if p.estimated_days <= 10 else ("Cut chat, multi-chain and advanced analytics.",)
            )
            return Argument(
                role,
                score,
                "Scope is survivable for one fast builder",
                (
                    "One deep LP feature",
                    "Optional integrations can be deferred",
                ),
                schedule_attacks,
                schedule_changes,
            )

        if role == CouncilRole.EVIDENCE_AUDITOR:
            evidence = set(p.evidence_plan)
            required = {
                "tx hash",
                "contract address",
                "raw benchmark outputs",
                "hash-chain ledger",
                "source labels",
            }
            missing = sorted(required - evidence)
            if not p.fixture_labeling:
                missing.append("fixture labeling")
            score = 96 - len(missing) * 14
            return Argument(
                role,
                score,
                "Evidence can be independently inspected",
                (
                    "Append-only trace",
                    "Source labels prevent demo/live confusion",
                ),
                tuple(f"Evidence gap: {item}" for item in missing),
                tuple(f"Add {item}" for item in missing),
                veto=bool(missing),
            )

        raise AssertionError(role)


class AdversarialCouncilPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        council = AdversarialCouncil(
            ledger=context.resolve("evidence.ledger"),
            llm_provider=context.optional("llm.provider"),
        )
        context.provide("design.council", council)
