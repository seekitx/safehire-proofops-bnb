"""Same-block Venus core lending observation; no repayment or custody authority."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from proofops.arena.financial_sources import COMPTROLLER
from proofops.arena.models import digest, utcnow
from proofops.decision.paid import ADDRESS, HASH, BscReader


async def observe_health(account: str, *, reader: BscReader | None = None) -> dict[str, Any]:
    if not ADDRESS.fullmatch(account) or int(account, 16) == 0:
        raise ValueError('A nonzero public BSC account is required')
    rpc = reader or BscReader()
    if int(await rpc.rpc('eth_chainId', []), 16) != 56:
        raise ValueError('Unexpected chain')
    number = int(await rpc.rpc('eth_blockNumber', []), 16) - 12
    block = await rpc.rpc('eth_getBlockByNumber', [hex(number), False])
    if (not isinstance(block, dict) or not HASH.fullmatch(str(block.get('hash', '')))
            or int(block['number'], 16) != number
            or not -5 <= utcnow().timestamp() - int(block['timestamp'], 16) <= 120):
        raise ValueError('Invalid or stale chain snapshot')
    reads = []

    async def call(to: str, signature: str, types: list[str], args: list[Any], outputs: list[str]) -> tuple[Any, ...]:
        data = '0x' + (keccak(text=signature)[:4] + encode(types, args)).hex()
        raw = await rpc.rpc('eth_call', [{'to': to, 'data': data},
                                       {'blockHash': block['hash'], 'requireCanonical': True}])
        result = decode(outputs, bytes.fromhex(raw[2:]))
        canonical = encode(outputs, result)
        if (bytes.fromhex(raw[2:]) != canonical and not (signature == 'getAccountSnapshot(address)'
                and bytes.fromhex(raw[2:]) == canonical + bytes(64))):
            raise ValueError(f'Unexpected Venus response encoding for {signature}: {len(bytes.fromhex(raw[2:]))} bytes')
        reads.append({'to': to, 'function': signature, 'calldata': data, 'result': raw})
        return result

    assets, oracle, protocol_liquidity, user_pool, vai = await asyncio.gather(
        call(COMPTROLLER, 'getAssetsIn(address)', ['address'], [account], ['address[]']),
        call(COMPTROLLER, 'oracle()', [], [], ['address']),
        call(COMPTROLLER, 'getAccountLiquidity(address)', ['address'], [account], ['uint256'] * 3),
        call(COMPTROLLER, 'userPoolId(address)', ['address'], [account], ['uint96']),
        call(COMPTROLLER, 'mintedVAIs(address)', ['address'], [account], ['uint256']),
    )
    if (len(assets[0]) > 16 or protocol_liquidity[0] != 0 or int(oracle[0], 16) == 0
            or user_pool[0] != 0 or vai[0] != 0):
        raise ValueError('Unsupported account or protocol error')
    rows = []
    collateral = debt = weighted = Decimal(0)
    for market in assets[0]:
        controller, snapshot, price, config = await asyncio.gather(
            call(market, 'comptroller()', [], [], ['address']),
            call(market, 'getAccountSnapshot(address)', ['address'], [account], ['uint256'] * 4),
            call(oracle[0], 'getUnderlyingPrice(address)', ['address'], [market], ['uint256']),
            call(COMPTROLLER, 'markets(address)', ['address'], [market], ['bool', 'uint256', 'bool', 'uint256', 'uint256', 'uint96', 'bool']),
        )
        if (controller[0].lower() != COMPTROLLER or snapshot[0] != 0 or price[0] <= 0
                or snapshot[3] <= 0 or not config[0] or not 0 <= config[3] <= 10**18):
            raise ValueError('Invalid market snapshot')
        supplied = Decimal(snapshot[1]) * snapshot[3] * price[0] / Decimal(10**54)
        borrowed = Decimal(snapshot[2]) * price[0] / Decimal(10**36)
        factor = Decimal(config[3]) / Decimal(10**18)
        collateral += supplied
        debt += borrowed
        weighted += supplied * factor
        rows.append({'market': market, 'supplied_usd': str(supplied),
                     'borrowed_usd': str(borrowed), 'liquidation_threshold': str(factor)})
    protocol_net = Decimal(protocol_liquidity[1] - protocol_liquidity[2]) / Decimal(10**18)
    difference = abs(weighted - debt - protocol_net)
    if difference > max(Decimal('0.01'), abs(protocol_net) * Decimal('0.000001')):
        raise ValueError('Per-market result disagrees with Venus; account needs further review')
    if (await rpc.canonical_block_hash(number)).lower() != block['hash'].lower():
        raise ValueError('Snapshot reorganized')
    value = {'schema_version': 'safehire-venus-health/1', 'chain_id': 56, 'account': account,
             'block_number': number, 'block_hash': block['hash'], 'block_timestamp': int(block['timestamp'], 16),
             'observed_at': utcnow().isoformat(), 'markets': rows,
             'collateral_usd': str(collateral), 'debt_usd': str(debt),
             'weighted_collateral_usd': str(weighted),
             'health_factor': str(weighted / debt) if debt else None,
             'status': 'no_debt' if not debt else 'shortfall' if protocol_liquidity[2] else 'no_shortfall',
             'protocol_net_liquidity_usd': str(protocol_net), 'cross_check_difference_usd': str(difference),
             'raw_reads': sorted(reads, key=lambda row: (row['to'], row['calldata'])),
             'trade_executed': False, 'settlement_authorized': False,
             'boundary': 'Venus core entered markets at one block, cross-checked against getAccountLiquidity. Stored interest and oracle prices can lag. Other pools and protocols are excluded. This is a point-in-time observation, not continuous protection or proof of account ownership.'}
    return {**value, 'observation_hash': digest(value)}
