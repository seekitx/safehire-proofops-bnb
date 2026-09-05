# SafeHire / ProofOps Agent Operating Contract

This file is the root operating contract for humans and coding agents working in this
repository. Read it before changing code, evidence, contest claims, deployment or
submission material.

## Mission

SafeHire is a **proof-carrying BNB Chain Agent marketplace**:

> Compare job-specific evidence, cap an Agent's authority, hire through an explicit
> ERC-8183 flow, and settle only against a reviewable delivery.

The product is not “another trading chatbot”. Its defensible innovation is the
trust-and-settlement envelope around financial Agents.

## Current truth — 2026-08-31

### Implemented and reviewable

- Four required BNB Chain categories are represented: rebalancing, grid trading,
  yield optimisation and health-factor monitoring.
- External BSC mainnet ERC-8004 registrations can be discovered and quoted.
- `/hire-live` prepares a wallet-confirmed ERC-8183 mainnet hire path.
- BSC Testnet Job #808 proves create → budget → approve → fund → deliver → settle.
- SafeHire contracts, ERC-8004 identity, transaction evidence and delivery are
  exposed through `/proof`.
- TermiX raw Agent/no-Agent outputs and a reproducible automated baseline exist.
- PancakeSwap live, same-block route evidence exists with explicit gas and
  non-profit boundaries.
- `/benchmark` supports human timing and blinded A/B review.
- Provider intake can validate another ERC-8004 identity without auto-listing it.
- CI tests Python, contracts, Agent Studio, security checks, Docker and the
  fail-closed submission gate.

### Manual proof still required

1. Capture the first **paid external mainnet delivery** from a live marketplace card.
2. Complete at least three **human no-Agent runs and independent blind reviews**.
3. Onboard a **second independent ERC-8004 operator**.
4. Keep judging-period hosting warm and publish a focused 2–3 minute demo.
5. The owner must review personal fields, prize wallet and contest terms before
   submitting.

### Not claimed

- Altana eligibility is not claimed without a real scoped session-key transaction
  and in-product revocation proof.
- Read-only quotes are not trades or realised profit.
- Sponsored analyses are not paid track records.
- Automated quality scores are not independent human research.
- The project self-audit is not an official BNB Chain score.

## Hard invariants

1. **Never fabricate adoption or evidence.** No generated transaction hash, paid
   delivery, testimonial, blind review, user count or profit claim.
2. **Never merge evidence modes.** `live`, `testnet_evidence`, `sponsored`,
   `caller_supplied` and `demo_fixture` remain machine-readable and visually distinct.
3. **Never let an LLM authorize money movement.** Simulation, policy, allowlist,
   caps, expiry, idempotency, wallet confirmation, human approval and kill switch
   remain deterministic.
4. **Never commit secrets.** Private keys, wallet keystores, API tokens, passwords,
   `.env`, `.env.local` and `.studio/wallets/` stay outside deployable and committed
   paths.
5. **Never silently widen mainnet authority.** A new target, selector, signing
   domain, amount, auto-funding path or unattended execution mode requires an
   explicit security review and updated evidence.
6. **Never present a self-score as official.** Official main-track numeric weights
   are not published; use separate criterion statuses and raw evidence.
7. **Never add scope before closing the vertical proof loop.** No extra chain,
   fifth category, generic chat, new contract or prediction model before the manual
   P0/P1 proof gates above are closed.
8. **Never leave stale contest statements unmarked.** Current status is governed by
   this file, `agent.md`, `docs/11_JUDGE_WINNING_STRATEGY_2026-08-31.md` and
   `docs/12_ADVERSARIAL_CONSENSUS_2026-08-31.md`.

## Task router

| Task | Start here | Then inspect |
|---|---|---|
| Understand current project state | `README.md` | `agent.md`, judge scorecard |
| Contest strategy or claims | `docs/11_JUDGE_WINNING_STRATEGY_2026-08-31.md` | official requirements, evidence files |
| Multi-role review | `docs/12_ADVERSARIAL_CONSENSUS_2026-08-31.md` | `src/proofops/plugins/adversarial.py` |
| Marketplace discovery/data | `src/proofops/services/live_agent_market.py` | live catalog, official source adapters |
| External ERC-8183 hire | `src/proofops/services/live_erc8183.py` | `/hire-live`, tests, evidence boundaries |
| Permissions/execution | `src/proofops/execution/` | contracts and threat model |
| Evidence or submission status | `src/proofops/services/submission.py` | `scripts/judge_scorecard.py`, `/proof` |
| TermiX work | `evidence/termix/` | benchmark lab and execution runbook |
| PancakeSwap work | `evidence/pancakeswap/` | capture script and LP policy |
| Agent Studio seller | `agent-studio/safehireagents/AGENTS.md` | nested rules take precedence |
| Build/package | `.github/workflows/` | `scripts/build_release.py` |

## Canonical document index

### Judge and submission

- `README.md` — 90-second project and evidence entry point.
- `agent.md` — task-oriented repository index.
- `docs/11_JUDGE_WINNING_STRATEGY_2026-08-31.md` — official-rubric strategy,
  winner patterns, innovation thesis and execution order.
- `docs/12_ADVERSARIAL_CONSENSUS_2026-08-31.md` — ten-role debate, disagreements,
  concessions and final consensus.
- `docs/PAST_WINNERS_AND_JUDGE_PATTERNS_2026-08-31.md` — official winner pattern
  analysis, updated after the live-hire implementation.
- `docs/MANUAL_COMPLETION_GATES_2026-08-31.md` — owner actions that code cannot do.
- `docs/HACKATHON_FINAL_SUBMISSION_CHECKLIST_2026-08-31.md` — submission fields and
  operational checks; treat older status prose as a dated snapshot.
- `apps/web/assets/judge-scorecard.html` — live judge-facing rubric map.
- `scripts/judge_scorecard.py` — deterministic machine-readable self-audit.

### Product and architecture

- `docs/01_COMPETITION_REQUIREMENTS.md`
- `docs/02_ARCHITECTURE.md`
- `docs/03_DOMAIN_AND_MODULE_DESIGN.md`
- `docs/04_PLUGIN_DECOUPLING.md`
- `docs/05_MULTI_AGENT_ADVERSARIAL_REVIEW.md`
- `docs/06_SECURITY_AND_THREAT_MODEL.md`
- `docs/07_CONSTRUCTION_BLUEPRINT.md`
- `docs/08_DEMO_AND_SUBMISSION.md`
- `docs/09_OPERATIONS.md`
- `docs/10_EXTERNAL_COMPLETION_CHECKLIST.md`

### Evidence

- `evidence/marketplace/live-agent-catalog.json`
- `evidence/sponsor-integration/erc8004-registration.json`
- `evidence/sponsor-integration/erc8183-job-808.json`
- `evidence/sponsor-integration/agent-studio-deployment.json`
- `evidence/pancakeswap/live-benefit-report.json`
- `evidence/termix/agent-advantage-report.json`
- `evidence/judging-notes/adversarial-decision.json`
- `evidence/judging-notes/adversarial-consensus-2026-08-31.json`
- `deployments/bsc-testnet.json`

## Required checks

```bash
python -m pytest -q
ruff check src apps tests scripts
mypy src apps scripts
python scripts/static_security_check.py
python scripts/submission_gate.py --allow-incomplete
python scripts/judge_scorecard.py --output judge-scorecard.json

cd contracts
npm ci --ignore-scripts
npm run compile
npm test
npm audit --omit=dev

cd ../agent-studio/safehireagents
corepack pnpm install --frozen-lockfile
corepack pnpm --dir app/agent build
```

Package only through `python scripts/build_release.py`; it regenerates a manifest
and excludes secret/build paths.

## Scope precedence

This root file governs the repository. A deeper `AGENTS.md` may add stricter rules
inside its subtree. In particular,
`agent-studio/safehireagents/AGENTS.md` is authoritative for Agent Studio signing,
wallet and deployment operations.


## 2026-09-05 evidence-first championship overlay

Read `docs/champion-2026-09-05/BLUEPRINT.zh-CN.md` and `docs/champion-2026-09-05/COMPETITOR_RESEARCH.zh-CN.md` before extending the marketplace.
Implementation entry points: `src/proofops/decision/`, `/decision`, `tests/champion/`.
Run `python -m pytest tests/champion` and the existing suite. Keep live source timestamps, treat category route parity as structure only, and never convert stored JSON booleans into verified paid outcomes.
The read-only replay requires matching ERC-8004 agent wallet, exact job/settlement/block, payment and deliverable commitment. It does not prove useful work, independent businesses, or profit.
Independent reviewer authentication, new provider adapters and live mainnet replay remain release gates listed in the blueprint. Do not mark them complete from synthetic tests.
