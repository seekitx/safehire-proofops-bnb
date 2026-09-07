"""A fixed BSC wallet watchlist, not token discovery or a trade recommendation."""
from __future__ import annotations

from decimal import Decimal, localcontext
from typing import Any

import httpx
from eth_abi.abi import decode, encode
from eth_abi.exceptions import DecodingError
from eth_utils.crypto import keccak

from proofops.arena.financial_sources import UNDERLYINGS
from proofops.arena.models import digest, utcnow
from proofops.decision.paid import ADDRESS, HASH, BscReader

# Chainlink standard BSC proxies; directory reviewed 2026-09-07.
# Age limits are application policy (heartbeat + tolerance), not guarantees.
ASSETS = {
    'BNB': (None, '0x0567f2323251f0aab15c8dfb1967e4e8a7d42aee', 120),
    'USDT': (UNDERLYINGS['venus-core-usdt'], '0xb97ad0e74fa7d920791e90258a6e2085088b4320', 1020),
    'USDC': (UNDERLYINGS['venus-core-usdc'], '0x51597f405303c4377e36123cbc172b13269ea163', 1020),
}


def price_from_round(values: tuple[Any, ...], block_time: int, max_age: int) -> Decimal:
    round_id, answer, started, updated, answered = values
    if (round_id <= 0 or answer <= 0 or started <= 0 or started > updated
            or updated > block_time or block_time - updated > max_age or answered < round_id):
        raise ValueError('Invalid or stale oracle round')
    with localcontext() as ctx:
        ctx.prec = 100
        return Decimal(answer) / Decimal(10**8)


def wallet_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with localcontext() as ctx:
        ctx.prec = 80
        total = sum((Decimal(r['reference_value_usd']) for r in rows
                     if r['reference_value_usd'] is not None), Decimal(0))
        missing = [r['symbol'] for r in rows if r['balance_raw'] is None
                   or (int(r['balance_raw']) > 0 and r['reference_value_usd'] is None)]
        for row in rows:
            value = row['reference_value_usd']
            row['share_of_priced_subset_pct'] = (
                str(Decimal(value) / total * 100) if value is not None and total > 0 else None)
        return {'priced_subset_value_usd': str(total), 'unvalued_or_unread_assets': missing,
                'watchlist_valuation_complete': not missing,
                'full_portfolio_complete': False,
                'concentration_warning': any(
                    r['share_of_priced_subset_pct'] is not None
                    and Decimal(r['share_of_priced_subset_pct']) >= 80 for r in rows),
                'concentration_scope': '80% threshold in the priced subset only; not a sell signal',
                'realized_profit_usd': None, 'historical_return_pct': None,
                'warnings': ['No complete token discovery, other chains, exchange accounts, debts or NFTs.',
                             'Oracle reference value is not an executable sale quote or purchase cost.',
                             'Pegged tokens can depeg; no deposit yield is inferred from wallet balances.']}


async def observe_wallet(account: str, *, reader: BscReader | None = None) -> dict[str, Any]:
    if not ADDRESS.fullmatch(account) or int(account, 16) == 0:
        raise ValueError('Expected a nonzero public BSC address, never a key')
    rpc = reader or BscReader()
    if int(await rpc.rpc('eth_chainId', []), 16) != 56:
        raise ValueError('Wrong chain')
    height = int(await rpc.rpc('eth_blockNumber', []), 16) - 12
    if height <= 0:
        raise ValueError('Invalid chain height')
    block = await rpc.rpc('eth_getBlockByNumber', [hex(height), False])
    if (not isinstance(block, dict) or not HASH.fullmatch(str(block.get('hash', '')))
            or int(block['number'], 16) != height):
        raise ValueError('Invalid block snapshot')
    timestamp = int(block['timestamp'], 16)
    if not -5 <= utcnow().timestamp() - timestamp <= 120:
        raise ValueError('Stale or future snapshot')
    reference = {'blockHash': block['hash'], 'requireCanonical': True}
    reads: list[dict[str, Any]] = []

    async def call(address: str, signature: str, outputs: list[str], *, wallet: bool = False) -> tuple[Any, ...]:
        data = '0x' + (keccak(text=signature)[:4] + (encode(['address'], [account]) if wallet else b'')).hex()
        raw = await rpc.rpc('eth_call', [{'to': address, 'data': data}, reference])
        reads.append({'method': 'eth_call', 'to': address, 'data': data, 'result': raw})
        encoded = bytes.fromhex(raw[2:])
        result = decode(outputs, encoded)
        if encode(outputs, result) != encoded:
            raise ValueError('Unexpected contract response')
        return result

    rows = []
    for symbol, (token, feed, max_age) in ASSETS.items():
        row: dict[str, Any] = {'symbol': symbol, 'token': token, 'balance_raw': None,
                               'balance': None, 'price_usd': None, 'reference_value_usd': None,
                               'price_feed': feed, 'errors': []}
        try:
            if token is None:
                raw = await rpc.rpc('eth_getBalance', [account, reference])
                reads.append({'method': 'eth_getBalance', 'account': account, 'result': raw})
                amount = int(raw, 16)
            else:
                decimals = (await call(token, 'decimals()', ['uint8']))[0]
                if decimals != 18:
                    raise ValueError('Token decimals changed')
                amount = (await call(token, 'balanceOf(address)', ['uint256'], wallet=True))[0]
            if not 0 <= amount < 2**256:
                raise ValueError('Invalid balance')
            with localcontext() as ctx:
                ctx.prec = 100
                row.update(balance_raw=str(amount), balance=str(Decimal(amount) / 10**18))
        except (ValueError, TypeError, KeyError, DecodingError, httpx.HTTPError, OSError) as exc:
            row['errors'].append('balance_unavailable:' + type(exc).__name__)
        try:
            if (await call(feed, 'decimals()', ['uint8']))[0] != 8:
                raise ValueError('Feed decimals changed')
            values = await call(feed, 'latestRoundData()', ['uint80', 'int256', 'uint256', 'uint256', 'uint80'])
            price = price_from_round(values, timestamp, max_age)
            row.update(price_usd=str(price), price_updated_at=values[3],
                       round_id=str(values[0]), max_price_age_seconds=max_age)
            if row['balance'] is not None:
                with localcontext() as ctx:
                    ctx.prec = 100
                    row['reference_value_usd'] = str(Decimal(row['balance']) * price)
        except (ValueError, TypeError, KeyError, DecodingError, httpx.HTTPError, OSError) as exc:
            row['errors'].append('price_unavailable:' + type(exc).__name__)
        rows.append(row)
    if (await rpc.canonical_block_hash(height)).lower() != block['hash'].lower():
        raise ValueError('Snapshot reorganized; discard all results')
    if utcnow().timestamp() - timestamp > 120:
        raise ValueError('Collection exceeded freshness window')
    observation = {'schema_version': 'safehire-wallet-observation/1', 'account': account,
                   'chain_id': 56, 'block_number': height, 'block_hash': block['hash'],
                   'block_timestamp': timestamp, 'observed_at': utcnow().isoformat(),
                   'assets': rows, 'summary': wallet_summary(rows), 'raw_reads': reads,
                   'account_ownership_verified': False, 'settlement_authorized': False,
                   'trust_boundary': 'Server read from one trusted RPC, not a consensus proof. Fixed three-asset watchlist only. No transaction authorization or automatic allocation.'}
    return {**observation, 'observation_hash': digest(observation)}
