from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from proofops.harness.contracts import HarnessPlugin, PluginContext

REQUIRED_CATEGORIES = {
    "rebalancing",
    "grid_trading",
    "yield_optimisation",
    "health_factor_monitoring",
}
REQUIRED_DECISION_SIGNALS = {
    "freshness",
    "identity",
    "price",
    "reputation",
    "feedback",
    "risk_boundary",
}


class CouncilRole(str, Enum):
    BNB_MAIN_JUDGE = "bnb_main_judge"
    BNB_DATA_QUALITY_JUDGE = "bnb_data_quality_judge"
    BNB_DIVERSITY_JUDGE = "bnb_diversity_judge"
    TERMIX_SPONSOR_JUDGE = "termix_sponsor_judge"
    PANCAKE_DEFI_REVIEWER = "pancake_defi_reviewer"
    ALTANA_SESSION_REVIEWER = "altana_session_reviewer"
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
    category_depth: tuple[str, ...] = (
        "rebalancing",
        "grid_trading",
        "yield_optimisation",
        "health_factor_monitoring",
    )
    decision_data_signals: tuple[str, ...] = (
        "freshness",
        "identity",
        "price",
        "reputation",
        "feedback",
        "risk_boundary",
    )
    live_hire_path: bool = True
    provider_count: int = 1
    paid_external_deliveries: int = 0
    human_blind_reviews: int = 0
    altana_live_session: bool = False

    @classmethod
    def safehire_default(cls) -> Proposal:
        return cls(
            title="SafeHire / ProofOps",
            problem="Users cannot verify which DeFi agent deserves scoped access to their money.",
            user_path=(
                "discover",
                "compare",
                "preview",
                "limit",
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
    """Ten deterministic reviewers that cannot vote away evidence or safety gaps.

    The council is intentionally stricter than a marketing review. Optional LLM
    elaboration may add questions, but the deterministic score and vetoes remain
    authoritative and reproducible.
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
            "The judge path must activate a live BSC Agent without a dead end.",
            "All four official categories must have equal, category-specific depth.",
            "Decision data must expose source, freshness and uncertainty.",
            "AgentProof must be deterministic and capped by evidence quality.",
            "AI cannot bypass simulation, policy, permission or human approval.",
            "Fixtures, sponsored analyses and paid deliveries must never be conflated.",
            "TermiX evidence must retain three same-task raw output pairs.",
            "Altana must not be claimed without a real session-key transaction and revocation proof.",
            "No self-audit may be presented as an official BNB Chain score.",
        )
        deferred = (
            "General-purpose AI chat",
            "Multi-chain expansion",
            "A fifth Agent category",
            "Complex microservice split",
            "Mainnet unattended execution",
            "Additional smart contracts without a judge-visible outcome",
            "Altana integration unless the complete live session flow can be evidenced",
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
            score = 94
            main_attacks: list[str] = []
            main_changes: list[str] = []
            if len(p.user_path) > 8:
                score -= 12
                main_attacks.append("The judge path is too long.")
                main_changes.append("Reduce the demo to one discover-to-receipt route.")
            if p.uses_generic_chat:
                score -= 18
                main_attacks.append("Generic chat dilutes the marketplace outcome.")
                main_changes.append("Keep conversation optional; lead with a concrete hire.")
            if not p.live_bsc_plan:
                score -= 45
                main_attacks.append("Agents are not planned to be live on BSC.")
                main_changes.append("Deploy callable BSC Agent identities and preserve registration proof.")
            if not p.live_hire_path:
                score -= 35
                main_attacks.append("Discovery ends before activation or settlement.")
                main_changes.append("Connect the live card to quote, ERC-8183 funding, delivery and receipt.")
            veto = not p.live_bsc_plan or not p.live_hire_path
            return Argument(
                role,
                score,
                "Strong BNB-native trust and settlement layer",
                (
                    "The problem is specific to agentic finance",
                    "The product has a short, inspectable path",
                ),
                tuple(main_attacks),
                tuple(main_changes),
                veto=veto,
            )

        if role == CouncilRole.BNB_DATA_QUALITY_JUDGE:
            signals = set(p.decision_data_signals)
            missing = sorted(REQUIRED_DECISION_SIGNALS - signals)
            score = 94 - len(missing) * 10
            data_attacks = [f"Missing decision signal: {item}" for item in missing]
            data_changes = [f"Expose {item} with source and timestamp." for item in missing]
            if p.paid_external_deliveries < 1:
                score -= 8
                data_attacks.append("No external paid delivery has become a verified track record.")
                data_changes.append("Complete one bounded external paid hire and attach the delivery receipt.")
            if p.human_blind_reviews < 3:
                score -= 4
                data_attacks.append("Quality evidence is still an automated baseline, not independent review.")
                data_changes.append("Complete three independent blinded output reviews.")
            return Argument(
                role,
                max(score, 0),
                "Decision data is broad, but outcome history is still conditional",
                (
                    "Freshness and source boundaries are first-class",
                    "Indexer signals and SafeHire observations remain separate",
                ),
                tuple(data_attacks),
                tuple(data_changes),
                veto=len(missing) >= 3,
            )

        if role == CouncilRole.BNB_DIVERSITY_JUDGE:
            categories = set(p.category_depth)
            missing = sorted(REQUIRED_CATEGORIES - categories)
            extra = sorted(categories - REQUIRED_CATEGORIES)
            score = 95 - len(missing) * 20
            diversity_attacks = [f"Missing category depth: {item}" for item in missing]
            diversity_changes = [f"Add a callable, category-specific {item} workflow." for item in missing]
            if extra:
                score -= 4
                diversity_attacks.append(f"Non-required categories dilute focus: {', '.join(extra)}")
                diversity_changes.append("Defer extra categories until all four official categories are equally deep.")
            if p.provider_count < 2:
                score -= 8
                diversity_attacks.append("All live listings currently come from one operator.")
                diversity_changes.append("Onboard a second independent ERC-8004 provider.")
            return Argument(
                role,
                max(score, 0),
                "Four-category parity is present; supplier diversity is the next proof",
                (
                    "Every official category has a dedicated skill",
                    "The same evidence envelope can compare heterogeneous agents",
                ),
                tuple(diversity_attacks),
                tuple(diversity_changes),
                veto=bool(missing),
            )

        if role == CouncilRole.TERMIX_SPONSOR_JUDGE:
            has_termix = any("TermiX" in item for item in p.sponsor_integrations)
            score = 91 if has_termix else 48
            termix_attacks: list[str] = []
            termix_changes: list[str] = []
            if not has_termix:
                termix_attacks.append("No three-task agent-versus-no-agent report.")
                termix_changes.append("Add three same-input comparisons with complete raw outputs.")
            if p.human_blind_reviews < 3:
                score -= 12
                termix_attacks.append("The published quality delta is not independently blinded.")
                termix_changes.append("Use the benchmark lab to collect three human runs and blind reviews.")
            return Argument(
                role,
                max(score, 0),
                "Structurally eligible, but the strongest quality claim still needs people",
                (
                    "Raw outputs and hashes are reproducible",
                    "Financial and safety-sensitive tasks are included",
                ),
                tuple(termix_attacks),
                tuple(termix_changes),
                veto=not has_termix,
            )

        if role == CouncilRole.PANCAKE_DEFI_REVIEWER:
            has_pancake = any("Pancake" in item for item in p.sponsor_integrations)
            score = 90 if has_pancake else 55
            pancake_attacks: list[str] = []
            pancake_changes: list[str] = []
            if not has_pancake:
                pancake_attacks.append("No protocol-native trader or LP benefit.")
                pancake_changes.append("Make the flagship workflow produce a measurable PancakeSwap benefit.")
            if p.paid_external_deliveries < 1:
                score -= 4
                pancake_attacks.append("The current measurable benefit is quoted, not realised by a paid external job.")
                pancake_changes.append("Bind one bounded hire to a fresh quote or LP decision and preserve the receipt.")
            return Argument(
                role,
                max(score, 0),
                "Protocol-native benefit is measurable and honestly bounded",
                (
                    "Same-block route comparisons are reproducible",
                    "Gas assumptions and execution boundaries are disclosed",
                ),
                tuple(pancake_attacks),
                tuple(pancake_changes),
            )

        if role == CouncilRole.ALTANA_SESSION_REVIEWER:
            claims_altana = any("Altana" in item for item in p.sponsor_integrations)
            if not claims_altana:
                return Argument(
                    role,
                    88,
                    "Altana is correctly treated as unclaimed scope",
                    (
                        "The project does not borrow eligibility from a logo",
                        "Existing permission controls remain useful to the main track",
                    ),
                    (),
                    (),
                )
            altana_attacks: tuple[str, ...] = ()
            altana_changes: tuple[str, ...] = ()
            score = 92
            if not p.altana_live_session:
                score = 42
                altana_attacks = ("Altana is named without a live session-key transaction and revocation proof.",)
                altana_changes = (
                    "Create a real scoped session, execute through it, revoke it in-product and attach Explorer evidence.",
                )
            return Argument(
                role,
                score,
                "Altana claim is evidence-gated",
                ("Scoped permissions align with the track",),
                altana_attacks,
                altana_changes,
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
            score = 96 - len(missing) * 12
            return Argument(
                role,
                score,
                "Fail closed with independent execution authority",
                (
                    "LLM output is advisory",
                    "Revocation, idempotency and approval are explicit",
                ),
                tuple(f"Missing control: {item}" for item in missing),
                tuple(f"Implement {item}." for item in missing),
                veto=bool(missing),
            )

        if role == CouncilRole.SYSTEM_ARCHITECT:
            modular = "modular_monolith" in p.architecture
            score = 92 if modular else 66
            architect_attacks = () if modular else ("Service splitting raises contest-time failure risk.",)
            architect_changes = (
                ()
                if modular
                else ("Use a modular monolith and isolate only signing and execution.",)
            )
            return Argument(
                role,
                score,
                "Bounded plugin architecture",
                (
                    "Capabilities can be replaced without rewriting the product",
                    "The deterministic execution boundary stays isolated",
                ),
                architect_attacks,
                architect_changes,
            )

        if role == CouncilRole.SOLO_BUILDER_SCHEDULE_ATTACKER:
            score = 93 if p.estimated_days <= 10 else max(40, int(100 - p.estimated_days * 4))
            schedule_attacks = () if p.estimated_days <= 10 else ("Scope exceeds a solo contest window.",)
            schedule_changes = (
                ()
                if p.estimated_days <= 10
                else ("Cut chat, extra chains, extra contracts and advanced analytics.",)
            )
            return Argument(
                role,
                score,
                "The remaining scope is survivable only if manual proof comes first",
                (
                    "The product already has an end-to-end skeleton",
                    "Optional sponsor work can be deferred",
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
            score = 97 - len(missing) * 14
            evidence_attacks = [f"Evidence gap: {item}" for item in missing]
            evidence_changes = [f"Add {item}." for item in missing]
            if p.paid_external_deliveries < 1:
                score -= 4
                evidence_attacks.append("No paid external delivery can yet be audited.")
                evidence_changes.append("Capture the first external mainnet delivery without rewriting history.")
            return Argument(
                role,
                max(score, 0),
                "Evidence is inspectable and claims are bounded",
                (
                    "The append-only ledger catches silent edits",
                    "Live, testnet, sponsored and fixture modes are distinct",
                ),
                tuple(evidence_attacks),
                tuple(evidence_changes),
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
