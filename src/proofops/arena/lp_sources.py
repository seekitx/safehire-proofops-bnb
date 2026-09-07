"""Fixed-contract, block-bound PancakeSwap V3 BNB/USDT position observations."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from proofops.arena.models import TaskSpec, digest, utcnow
from proofops.decision.paid import HASH, BscReader

# https://developer.pancakeswap.finance/contracts/v3/addresses, checked 2026-09-08.
MANAGER = '0x46a15b0b27311cedf172ab29e4f4766fbe7f4364'
FACTORY = '0x0bfbcf9fa4f9c56b0f40a671ad40e0805a091865'
PAIR = {'0x55d398326f99059ff775485246999027b3197955',
        '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'}
POSITION_TYPES = ['uint96', 'address', 'address', 'address', 'uint24', 'int24', 'int24',
                  'uint128', 'uint256', 'uint256', 'uint128', 'uint128']


async def observe_lp(position_id: int, *, reader: BscReader | None = None) -> dict[str, Any]:
    if isinstance(position_id, bool) or not 0 < position_id < 2**53:
        raise ValueError('A positive safe-integer position NFT ID is required')
    rpc = reader or BscReader()
    if int(await rpc.rpc('eth_chainId', []), 16) != 56:
        raise ValueError('LP reader returned the wrong chain')
    number = int(await rpc.rpc('eth_blockNumber', []), 16) - 12
    block = await rpc.rpc('eth_getBlockByNumber', [hex(number), False])
    if (not isinstance(block, dict) or not HASH.fullmatch(str(block.get('hash', '')))
            or int(block['number'], 16) != number):
        raise ValueError('LP block reference mismatch')
    timestamp = int(block['timestamp'], 16)
    if not -5 <= utcnow().timestamp() - timestamp <= 120:
        raise ValueError('LP chain snapshot is stale or in the future')
    block_hash = block['hash']
    reads: list[dict[str, str]] = []

    async def call(to: str, function: str, types: list[str], args: list[Any], outputs: list[str]) -> tuple[Any, ...]:
        data = '0x' + (keccak(text=function)[:4] + encode(types, args)).hex()
        raw = await rpc.rpc('eth_call', [{'to': to, 'data': data},
                                       {'blockHash': block_hash, 'requireCanonical': True}])
        if not isinstance(raw, str) or not raw.startswith('0x'):
            raise ValueError('LP contract returned invalid bytes')
        decoded = decode(outputs, bytes.fromhex(raw[2:]))
        if encode(outputs, decoded).hex() != raw[2:]:
            raise ValueError('Noncanonical LP contract response')
        reads.append({'to': to, 'function': function, 'calldata': data, 'result': raw})
        return decoded

    position, owner, factory = await asyncio.gather(
        call(MANAGER, 'positions(uint256)', ['uint256'], [position_id], POSITION_TYPES),
        call(MANAGER, 'ownerOf(uint256)', ['uint256'], [position_id], ['address']),
        call(MANAGER, 'factory()', [], [], ['address']),
    )
    token0, token1, fee, lower, upper, liquidity = position[2:8]
    if (factory[0].lower() != FACTORY or {token0.lower(), token1.lower()} != PAIR
            or int(owner[0], 16) == 0 or liquidity <= 0):
        raise ValueError('Only nonempty reviewed BNB/USDT PancakeSwap V3 positions are supported')
    pool = (await call(FACTORY, 'getPool(address,address,uint24)',
                       ['address', 'address', 'uint24'], [token0, token1, fee], ['address']))[0]
    if int(pool, 16) == 0:
        raise ValueError('No reviewed pool exists for this position')
    slot, spacing, pool_factory, p0, p1, pool_fee = await asyncio.gather(
        call(pool, 'slot0()', [], [], ['uint160', 'int24', 'uint16', 'uint16', 'uint16', 'uint32', 'bool']),
        call(pool, 'tickSpacing()', [], [], ['int24']),
        call(pool, 'factory()', [], [], ['address']),
        call(pool, 'token0()', [], [], ['address']), call(pool, 'token1()', [], [], ['address']),
        call(pool, 'fee()', [], [], ['uint24']),
    )
    if (pool_factory[0].lower() != FACTORY or p0[0].lower() != token0.lower()
            or p1[0].lower() != token1.lower() or pool_fee[0] != fee
            or spacing[0] <= 0 or lower >= upper or lower % spacing[0] or upper % spacing[0]
            or not -887272 <= slot[1] <= 887272 or not slot[6] or slot[0] <= 0):
        raise ValueError('LP pool identity, range or state mismatch')
    decimals = await asyncio.gather(*(call(token, 'decimals()', [], [], ['uint8']) for token in (token0, token1)))
    if any(row[0] != 18 for row in decimals):
        raise ValueError('Reviewed LP token decimals changed')
    if (await rpc.canonical_block_hash(number)).lower() != block_hash.lower():
        raise ValueError('LP block reorganized during collection')
    observation = {
        'schema_version': 'safehire-lp-observation/1', 'chain_id': 56,
        'block_number': number, 'block_hash': block_hash, 'block_timestamp': timestamp,
        'observed_at': utcnow().isoformat(), 'position_id': position_id, 'owner': owner[0],
        'manager': MANAGER, 'factory': FACTORY, 'pool': pool, 'token0': token0, 'token1': token1,
        'fee': fee, 'current_tick': slot[1], 'lower_tick': lower, 'upper_tick': upper,
        'tick_spacing': spacing[0], 'liquidity_raw': str(liquidity),
        'token0_decimals': 18, 'token1_decimals': 18, 'in_range': lower <= slot[1] < upper,
        'raw_reads': sorted(reads, key=lambda row: (row['to'], row['calldata'])),
        'ownership_by_caller_verified': False, 'financial_inputs_authenticated': False,
        'settlement_authorized': False,
        'trust_boundary': 'Single trusted RPC observation. Owner is public chain data, not caller authentication. No gas, slippage, profit, fee income or permission to rebalance is certified.',
    }
    return {**observation, 'observation_hash': digest(observation)}


def source_lp_task(template: TaskSpec, observation: dict[str, Any]) -> TaskSpec:
    if template.category != 'rebalancing':
        raise ValueError('An LP range task is required')
    value = template.to_dict()
    value['inputs'].update({
        'current_tick': observation['current_tick'], 'old_lower_tick': observation['lower_tick'],
        'old_upper_tick': observation['upper_tick'], 'tick_spacing': observation['tick_spacing'],
        'liquidity_raw': int(observation['liquidity_raw']),
        'token0_decimals': observation['token0_decimals'], 'token1_decimals': observation['token1_decimals'],
    })
    value['snapshot'] = {'chain_id': 56, 'block_number': observation['block_number'],
                         'block_hash': observation['block_hash'],
                         'observed_at': datetime.fromtimestamp(observation['block_timestamp'], UTC).isoformat(),
                         'source': f"pancakeswap_v3_position_{observation['position_id']}_rpc_with_caller_cost_and_width_assumptions"}
    return TaskSpec.model_validate(value)
