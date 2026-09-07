# Explicit review: official SDK quotes and LP observations

Reviewed 2026-09-08. This change permits one configured second endpoint to prepare unsigned orders; it does not authorize automatic payment, LP execution, settlement, or a claim of independent business ownership.

## Signing compatibility

Reference: official bnb-chain/bnbagent-sdk commit `bab27109237d509c780a36cf831dcfce70aabafe`, `python/bnbagent/erc8183/negotiation.py`. The adapter is explicitly selected with `bnbagent-sdk-v1`; the existing SafeHire format is unchanged. A recorded real public signature is replayed offline in regression tests.

The SDK response hash excludes negotiated_at, while the signed job description binds it. Its signed terms project deliverables, quality_standards and success_criteria. Evaluation metadata is not signed and never selects our evaluator: the exact fixed reviewed OptimisticPolicy and router are included in signed quality text. The adapter rejects unknown formats, changed tasks/terms/prices/contracts/chains and expired signatures. It also rejects bracket-containing or non-ASCII task/quality strings that the SDK might sanitize. This prevents silently modifying structured task data; array-based tasks are not supported by this adapter.

The configured provider wallet must match the recovered signer and a current ERC-8004 getAgentWallet read at a canonical block. Registration evidence includes current owner/wallet/tokenURI, not an invented creation receipt. A signature and registry entry do not prove useful delivery.

## Time and money

The live fixed policy reports a seven-day dispute window. The previous seven-day total-order cap could never accommodate that window plus delivery. Delivery is now capped at one day and the total at eight days plus thirty minutes; the actual expiry uses delivery plus the observed dispute window and existing buffer. The UI separately displays delivery ETA, dispute days and final expiry. The quote price cap, payment token, commerce contract, router and policy are unchanged. There is no new target, selector, private key or automatic funding. A seven-day lock may outlast the contest deadline.

## LP source limits

Read-only calls are pinned to reviewed PancakeSwap V3 manager/factory on chain 56 and the BNB/USDT pair. Position, pool identity, fee, decimals, range and liquidity use one block hash, confirmed again after collection. Wrong chain, stale/reorganized blocks, empty positions and malformed bytes fail closed. No execute/activate endpoint is called. Source observations do not authenticate the caller as owner. Range width, USD costs and slippage remain explicit assumptions; this is not a profit certificate or a trade.

The public supplier demonstration position 7319347 is tiny. Supplier-reported P&L and rebalance counts are not accepted as independently verified performance. A signed quote and unsigned transaction plan were observed successfully; payment, delivery format compatibility and useful paid output remain unproven.

Browser precision review: uint128 liquidity is parsed from the original JSON token and kept as decimal text during form edits, then serialized as the exact original integer. The server task format and hash domain remain unchanged. Browsers lacking lossless JSON primitives refuse the operation with an update-browser message. Desktop and mobile-width Chromium tests save, reload and export `327142007496340585` without changing any digit.
