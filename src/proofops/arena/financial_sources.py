"""Bounded, read-only Venus core observations. Never a full-portfolio certificate."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal, localcontext
from typing import Any

from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from proofops.arena.models import TaskSpec, digest, utcnow
from proofops.decision.paid import ADDRESS, HASH, BscReader

# VenusProtocol/venus-protocol deployments/bscmainnet, reviewed 2026-09-07.
# Pinned upstream revision: 15e950b0d24de79c25effea6e1412944aa5acb2a.
COMPTROLLER = '0xfd36e2c2a6789db23113685031d7f16329158384'
MARKETS = {
    'venus-core-usdt': '0xfd5840cd36d94d7229439859c0112a4185bc0255',
    'venus-core-usdc': '0xeca88125a5adbe82614ffc12d0db554e2e2867c8',
}
UNDERLYINGS = {
    'venus-core-usdt': '0x55d398326f99059ff775485246999027b3197955',
    'venus-core-usdc': '0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d',
}


def annualized_supply_pct(rate_raw: int, elapsed_seconds: int, blocks: int) -> str:
    """Daily-compounded projection at the observed block cadence, NOT realized return."""
    if not 0 <= rate_raw <= 10**14 or not 60 <= elapsed_seconds <= 3600 or blocks <= 0:
        raise ValueError('Unsupported rate or block-time window; no annualization guessed')
    with localcontext() as ctx:
        ctx.prec = 60
        daily_rate = Decimal(rate_raw) / Decimal(10**18) * 86400 * blocks / elapsed_seconds
        result = ((1 + daily_rate) ** 365 - 1) * 100
        if result > 1000:
            raise ValueError('Projected APY exceeds supported analysis range')
        return str(result.quantize(Decimal('0.00000001')))


async def observe_venus(account: str | None = None, *, reader: BscReader | None = None) -> dict[str, Any]:
    if account is not None and (not ADDRESS.fullmatch(account) or int(account, 16) == 0):
        raise ValueError('A nonzero public BSC address is required, never a private key')
    rpc = reader or BscReader()
    if int(await rpc.rpc('eth_chainId', []), 16) != 56:
        raise ValueError('Financial source returned the wrong chain')
    # Twelve blocks behind head, then anchor every contract call to this exact hash.
    head = int(await rpc.rpc('eth_blockNumber', []), 16)
    number = head - 12
    if number <= 1200:
        raise ValueError('Insufficient chain history')
    block, previous = await asyncio.gather(
        rpc.rpc('eth_getBlockByNumber', [hex(number), False]),
        rpc.rpc('eth_getBlockByNumber', [hex(number - 1200), False]),
    )
    if not isinstance(block, dict) or not isinstance(previous, dict):
        raise TypeError('Missing block-time observations')
    block_hash = str(block.get('hash', ''))
    if (not HASH.fullmatch(block_hash) or int(block['number'], 16) != number
            or int(previous['number'], 16) != number - 1200):
        raise ValueError('Block reference mismatch')
    timestamp = int(block['timestamp'], 16)
    if not -5 <= utcnow().timestamp() - timestamp <= 120:
        raise ValueError('Stale/future chain head')
    elapsed = timestamp - int(previous['timestamp'], 16)
    reads: list[dict[str, Any]] = []

    async def call(to: str, signature: str, types: list[str], args: list[Any], outputs: list[str]) -> tuple[Any, ...]:
        data = '0x' + (keccak(text=signature)[:4] + encode(types, args)).hex()
        raw = await rpc.rpc('eth_call', [{'to': to, 'data': data},
                                       {'blockHash': block_hash, 'requireCanonical': True}])
        if not isinstance(raw, str) or not raw.startswith('0x'):
            raise ValueError('Invalid contract response')
        encoded = bytes.fromhex(raw[2:])
        decoded = decode(outputs, encoded)
        canonical = encode(outputs, decoded)
        # Observed core deployment appends two zero words to these delegated reads.
        # Accept only that unambiguous zero suffix, not arbitrary trailing values.
        zero_padded = (signature in {'supplyRatePerBlock()', 'getAccountSnapshot(address)'}
                       and encoded == canonical + bytes(64))
        if canonical != encoded and not zero_padded:
            raise ValueError('Noncanonical contract response')
        reads.append({'to': to, 'function': signature, 'calldata': data, 'result': raw})
        return decoded

    rows = []
    for venue, market in MARKETS.items():
        controller, underlying, rate, accrued_at = await asyncio.gather(
            call(market, 'comptroller()', [], [], ['address']),
            call(market, 'underlying()', [], [], ['address']),
            call(market, 'supplyRatePerBlock()', [], [], ['uint256']),
            call(market, 'accrualBlockNumber()', [], [], ['uint256']),
        )
        if controller[0].lower() != COMPTROLLER or not 0 < accrued_at[0] <= number:
            raise ValueError('Unexpected Venus market controller/accrual block')
        if underlying[0].lower() != UNDERLYINGS[venue]:
            raise ValueError('Market underlying changed; contract review required')
        decimals = (await call(underlying[0], 'decimals()', [], [], ['uint8']))[0]
        if decimals != 18:
            raise ValueError('Unsupported underlying decimals')
        row: dict[str, Any] = {
            'venue_id': venue, 'vtoken': market, 'underlying': underlying[0],
            'underlying_decimals': decimals, 'supply_rate_per_block_raw': str(rate[0]),
            'projected_supply_apy_pct': annualized_supply_pct(rate[0], elapsed, 1200),
            'accrual_block_number': accrued_at[0],
        }
        if account is not None:
            error, balance, debt, exchange = await call(
                market, 'getAccountSnapshot(address)', ['address'], [account], ['uint256'] * 4)
            if error != 0 or exchange <= 0:
                raise ValueError('Venus could not read the account snapshot')
            row['position'] = {
                'vtoken_balance_raw': str(balance), 'borrow_balance_stored_raw': str(debt),
                'exchange_rate_stored_raw': str(exchange),
                'supplied_underlying_stored_raw': str(balance * exchange // 10**18),
                'account_ownership_verified': False,
                'fresh_interest_accrual_verified': False,
            }
        rows.append(row)
    if (await rpc.canonical_block_hash(number)).lower() != block_hash.lower():
        raise ValueError('Chain reorganized during collection; discard observations')
    if await rpc.canonical_block_hash(number - 1200) != previous['hash']:
        raise ValueError('Block-time window reorganized during collection')
    observation = {
        'schema_version': 'safehire-venus-observation/1', 'chain_id': 56,
        'block_number': number, 'block_hash': block_hash,
        'block_timestamp': timestamp, 'observed_at': utcnow().isoformat(), 'account': account,
        'markets': rows, 'raw_reads': sorted(reads, key=lambda r: (r['to'], r['calldata'])),
        'annualization': {'method': 'daily_compounding_constant_spot_rate_365_days',
                         'window_blocks': 1200, 'window_seconds': elapsed,
                         'window_start_block': number - 1200, 'window_start_hash': previous['hash'],
                         'rewards_included': False, 'forecast_not_guarantee': True},
        'scope': 'Two reviewed Venus core markets only; NOT a complete account portfolio',
        'financial_inputs_authenticated': False, 'settlement_authorized': False,
        'trust_boundary': 'Single trusted RPC observation, not a consensus proof. Stored balances and rate inputs may lag interest accrual. No USD price, withdrawal capacity, gas, tax, complete debt or liquidation safety certified. Token depeg and conversion risks are not priced.',
    }
    return {**observation, 'observation_hash': digest(observation)}


def source_yield_task(template: TaskSpec, observation: dict[str, Any], current_venue: str) -> TaskSpec:
    """Replace ONLY the snapshot and APYs, retaining explicit caller assumptions."""
    if template.category != 'yield_optimisation' or current_venue not in MARKETS:
        raise ValueError('Select a reviewed Venus current venue and a yield task')
    rates = {row['venue_id']: float(row['projected_supply_apy_pct']) for row in observation['markets']}
    value = template.to_dict()
    for venue in value['inputs']['venues']:
        if venue['venue_id'] not in rates:
            raise ValueError('Every venue must be a reviewed Venus core market')
        venue['apy_pct'] = rates[venue['venue_id']]
    value['inputs']['current_apy_pct'] = rates[current_venue]
    value['snapshot'] = {
        'chain_id': 56, 'block_number': observation['block_number'],
        'block_hash': observation['block_hash'],
        'observed_at': datetime.fromtimestamp(observation['block_timestamp'], UTC).isoformat(),
        'source': 'venus_core_rpc_rates_with_explicit_caller_cost_capacity_and_capital_assumptions',
    }
    return TaskSpec.model_validate(value)
