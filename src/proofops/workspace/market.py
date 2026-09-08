"""Fixed PancakeSwap BNB/USDT market observation for range alerts, not execution."""
from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from proofops.arena.lp_sources import FACTORY
from proofops.arena.models import digest, utcnow
from proofops.decision.paid import HASH, BscReader

POOL = '0x36696169c63e42cd08ce11f5deebbcebae652050'
USDT = '0x55d398326f99059ff775485246999027b3197955'
WBNB = '0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c'


async def observe_grid_market(*, reader: BscReader | None = None) -> dict[str, Any]:
    rpc = reader or BscReader()
    if int(await rpc.rpc('eth_chainId', []), 16) != 56:
        raise ValueError('Wrong chain')
    number = int(await rpc.rpc('eth_blockNumber', []), 16)-12
    block = await rpc.rpc('eth_getBlockByNumber', [hex(number), False])
    if (not isinstance(block, dict) or not HASH.fullmatch(str(block.get('hash', '')))
            or int(block['number'], 16) != number
            or not -5 <= utcnow().timestamp()-int(block['timestamp'], 16) <= 120):
        raise ValueError('Stale or malformed market block')
    reads: list[dict[str, Any]] = []
    async def call(to: str, fn: str, outputs: list[str], types: list[str] | None = None, args: list[Any] | None = None) -> tuple[Any, ...]:
        data='0x'+(keccak(text=fn)[:4]+encode(types or [], args or [])).hex()
        raw=await rpc.rpc('eth_call',[{'to':to,'data':data},{'blockHash':block['hash'],'requireCanonical':True}])
        value=decode(outputs,bytes.fromhex(raw[2:]))
        if encode(outputs,value).hex()!=raw[2:]:
            raise ValueError('Noncanonical market response')
        reads.append({'to':to,'function':fn,'data':data,'result':raw})
        return value
    slot, factory, t0, t1, fee, pool, d0, d1 = await asyncio.gather(
        call(POOL,'slot0()',['uint160','int24','uint16','uint16','uint16','uint32','bool']),
        call(POOL,'factory()',['address']),call(POOL,'token0()',['address']),call(POOL,'token1()',['address']),
        call(POOL,'fee()',['uint24']),call(FACTORY,'getPool(address,address,uint24)',['address'],['address','address','uint24'],[USDT,WBNB,500]),
        call(USDT,'decimals()',['uint8']),call(WBNB,'decimals()',['uint8']))
    if (factory[0].lower()!=FACTORY or t0[0].lower()!=USDT or t1[0].lower()!=WBNB
            or pool[0].lower()!=POOL or fee[0]!=500 or d0[0]!=18 or d1[0]!=18 or not slot[6] or slot[0]<=0):
        raise ValueError('Market identity changed')
    if (await rpc.canonical_block_hash(number)).lower()!=block['hash'].lower():
        raise ValueError('Market block reorganized')
    value={'chain_id':56, 'block_number':number, 'block_hash':block['hash'], 'observed_at':utcnow().isoformat(),
           'pool':POOL,'pair':'WBNB/USDT','price_usdt_per_wbnb':str(Decimal(2**192)/Decimal(slot[0])**2),
           'raw_reads':sorted(reads,key=lambda r:(r['to'],r['data'])), 'trade_executed':False,
           'boundary':'Spot price in one fixed pool, not USD fair value, TWAP, oracle or executable quote. USDT may depeg; no trade or automatic stop loss.'}
    return value | {'observation_hash':digest(value)}


def yield_comparison(observation: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    capital=Decimal(str(spec['capital']))
    days=Decimal(str(spec['days']))
    cost=Decimal(str(spec['cost']))
    current=spec['current_venue']
    rows=[]
    for market in observation['markets']:
        rate=Decimal(market['projected_supply_apy_pct'])/100
        gross=capital*((1+rate)**(days/365)-1)
        rows.append({'venue':market['venue_id'],'apy_pct':str(rate*100),'projected_net_usd':str(gross-(0 if market['venue_id']==current else cost))})
    hold=next(Decimal(r['projected_net_usd']) for r in rows if r['venue']==current)
    for row in rows:
        row['increment_vs_hold_usd']=str(Decimal(row['projected_net_usd'])-hold)
    best=max(rows,key=lambda r:Decimal(r['projected_net_usd']))
    return {'alternatives':rows,'best_under_assumptions':best['venue'],
            'triggered':Decimal(best['increment_vs_hold_usd'])>Decimal(str(spec['minimum_gain'])),
            'current_venue':current,'capacity':None,'exit_liquidity':None,'withdrawal_delay':None,
            'migration_ready':False,'trade_executed':False,
            'boundary':'Hypothetical capital, horizon and migration cost; constant APY and stablecoin parity assumptions. Capacity and exits are unknown; do not migrate automatically.'}
