# SafeHire ProofOps Agent Studio runtime

This is the official `@bnbagent/studio-cli@0.0.13` seller workspace for
SafeHire ProofOps. It exposes A2A, MCP and X402 faces while keeping one bounded
signer inside the generated runtime.

## What this agent sells

The ERC-8183 quote is a deterministic **0.1 U** price with the same hard upper
bound. After a job is funded, the value layer calls the public SafeHire API's
read-only `safehire_preview` tool and returns an evidence-labelled risk report.
It does not execute trades, transfer funds, approve tokens or promise profit.

Supported preview engines:

- `lp-guardian-demo` — LP range rebalancing analysis
- `grid-sentinel-demo` — bounded grid proposal
- `yield-scout-demo` — risk-adjusted yield comparison
- `hf-shield-demo` — lending health-factor analysis

The `-demo` suffix is intentional until each public endpoint has real BSC
registration and transaction evidence. Do not rename it or mark it live merely
for a submission screenshot.

## Safety boundaries

- `.studio/` contains the encrypted keystore and local secrets; it is ignored.
- Wallet signing remains fixed in `app/agent/src/signing.ts`; it is never an
  LLM tool.
- `safehire_preview` only calls `POST /api/agents/{id}/invoke`; it cannot create
  a permission, approve a task or execute an action.
- Non-local `SAFEHIRE_API_BASE_URL` must use HTTPS.
- LLM auto-renew and the spending budget are disabled by default.
- The sibling B402 route is intentionally FREE (`price_usd = "0"`) so missing
  Binance merchant credentials cannot block the core ERC-8183 seller. This is
  a passthrough route, not proof of a paid B402 transaction.

## Local checks

From this directory:

```bash
corepack pnpm install --frozen-lockfile
corepack pnpm --dir app/agent build
npx --yes --package @bnbagent/studio-cli@0.0.13 bag doctor
```

For local development, place secrets only in `.studio/.env.local` and set:

```text
SAFEHIRE_API_BASE_URL=http://127.0.0.1:8000
```

Do not put a wallet password or API key on the command line. `bag doctor` will
remain incomplete until an isolated BSC Testnet wallet, LLM/storage credentials
and paid B402 merchant credentials are provided. Keep the route at price zero
until that separate prize path is actually ready; the 0.1 U ERC-8183 hire is
the canonical paid demo.

## Deploy boundary

Deployment is deliberately not automated by this repository because it needs
the owner's cloud/GitHub login and isolated wallet. Use one visible provider:

```bash
npx --yes --package @bnbagent/studio-cli@0.0.13 bag deploy prepare
npx --yes --package @bnbagent/studio-cli@0.0.13 bag deploy --provider bnb
npx --yes --package @bnbagent/studio-cli@0.0.13 bag deploy verify --provider bnb
```

The BNB trial is temporary and testnet-only. Use `--provider aws` or
`--provider azure` only after reviewing the corresponding official Studio
playbook and account costs.
