# External provider compatibility handoff

Observed 2026-09-08 against the existing Brain On BNB yield route. The exact public synthetic request and returned response are preserved in `evidence/marketplace/provider-compatibility-2026-09-08.json`. No wallet address, private key or payment was used. This packet has not been sent as a message to the provider.

The provider returns accepted=true, price 0.10 U, service yield_plan and payment instructions, but no complete signed negotiation envelope. This is a compatibility failure, not evidence that a paid job failed or that the provider is malicious.

Required integration work:

1. Return request, request_hash, response, response_hash, chain_id, verifying_contract, negotiation_hash and provider_sig in one negotiation object. Exact hashing/signature rules are in `src/proofops/integrations/erc8183_quote.py`; do not guess a different serialization or signing domain.
2. Preserve the requested task, nonce and non-price terms. Sign with the registered provider wallet or its supported contract signature mechanism. Include the validated price, token and validity window.
3. Accept the structured Arena terms only if the actual delivery can return the requested safehire-proposal/2 task hash, snapshot hash, agent reference, action and parameters. Narrative analysis is not a substitute.
4. Provide an integration sample that passes `scripts/probe_arena_provider.py` and the existing verifier. Only then ask the owner to review a real priced job and wallet transactions.
5. Preserve exact delivery content and commitment for acceptance against the frozen task. Keep payment, settlement, policy acceptance and financial usefulness as separate claims.

The rebalancing route is explicitly portfolio analysis, not LP range execution. A compatible LP service is still required for that category. The UI refuses to carry an LP task into this incompatible route.
