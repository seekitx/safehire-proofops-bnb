"""Fresh action preparation. Draft calldata and eth_call never grant signing authority."""
from __future__ import annotations

import asyncio
from decimal import ROUND_CEILING, Decimal
from typing import Any

from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak

from proofops.arena.financial_sources import COMPTROLLER, MARKETS, UNDERLYINGS, observe_venus
from proofops.arena.health_sources import observe_health
from proofops.arena.lp_sources import MANAGER, observe_lp
from proofops.arena.models import digest, utcnow
from proofops.arena.planners import grid_metrics, lp_inventory, lp_range
from proofops.decision.paid import BscReader
from proofops.workspace.market import observe_grid_market, yield_comparison

D = Decimal


def calldata(signature: str, types: list[str], args: list[Any]) -> str:
    return '0x' + (keccak(text=signature)[:4] + encode(types, args)).hex()


class BlockCalls:
    def __init__(self, observation: dict[str, Any], reader: BscReader | None = None):
        self.observation = observation
        self.reader = reader or BscReader()
        self.reads: list[dict[str, Any]] = []

    async def call(self, to: str, signature: str, outputs: list[str],
                   types: list[str] | None = None, args: list[Any] | None = None,
                   sender: str | None = None) -> tuple[Any, ...]:
        tx = {'to': to, 'data': calldata(signature, types or [], args or [])}
        if sender:
            tx['from'] = sender
        try:
            raw = await self.reader.rpc('eth_call', [tx, {'blockHash': self.observation['block_hash'], 'requireCanonical': True}])
        except ValueError as exc:
            raise ValueError('Read failed: '+signature) from exc
        blob = bytes.fromhex(raw[2:])
        result = decode(outputs, blob)
        canonical = encode(outputs, result)
        # Reviewed legacy delegator view wrapper can append exactly two zero words.
        padded = signature in {'getCash()', 'exchangeRateStored()', 'getAccountSnapshot(address)'} and blob == canonical + bytes(64)
        if blob != canonical and not padded:
            raise ValueError('Noncanonical response for ' + signature)
        self.reads.append({'transaction': tx, 'function': signature, 'result': raw})
        return result

    async def finish(self) -> None:
        if (await self.reader.canonical_block_hash(self.observation['block_number'])).lower() != self.observation['block_hash'].lower():
            raise ValueError('Action snapshot reorganized; discard the plan')
        if not -5 <= utcnow().timestamp() - self.observation['block_timestamp'] <= 120:
            raise ValueError('Action snapshot expired while preparing')


async def venus_capacity(observation: dict[str, Any], *, reader: BscReader | None = None) -> dict[str, Any]:
    calls = BlockCalls(observation, reader)
    paused = (await calls.call(COMPTROLLER, 'protocolPaused()', ['bool']))[0]
    rows = []
    for market in observation['markets']:
        venue = market['venue_id']
        if market['vtoken'].lower() != MARKETS[venue] or market['underlying'].lower() != UNDERLYINGS[venue]:
            raise ValueError('Unreviewed market')
        cash, borrows, reserves, cap, mint, redeem = await asyncio.gather(
            calls.call(MARKETS[venue], 'getCash()', ['uint256']),
            calls.call(MARKETS[venue], 'totalBorrows()', ['uint256']),
            calls.call(MARKETS[venue], 'totalReserves()', ['uint256']),
            calls.call(COMPTROLLER, 'supplyCaps(address)', ['uint256'], ['address'], [MARKETS[venue]]),
            calls.call(COMPTROLLER, 'actionPaused(address,uint8)', ['bool'], ['address', 'uint8'], [MARKETS[venue], 0]),
            calls.call(COMPTROLLER, 'actionPaused(address,uint8)', ['bool'], ['address', 'uint8'], [MARKETS[venue], 1]),
        )
        supplied = cash[0] + borrows[0] - reserves[0]
        if supplied < 0:
            raise ValueError('Invalid market accounting')
        # Venus Core cap zero disables minting, unlike Compound's unlimited convention.
        room = max(0, cap[0] - supplied)
        rows.append({'venue_id': venue, 'cash_token_units': str(D(cash[0])/10**18),
                     'supply_room_token_units': str(D(room)/10**18), 'supply_cap_raw': str(cap[0]),
                     'mint_paused': paused or mint[0], 'redeem_paused': paused or redeem[0],
                     'account_withdrawal_verified': False})
    await calls.finish()
    return {'markets': rows, 'block_number': observation['block_number'], 'block_hash': observation['block_hash'],
            'raw_reads': calls.reads, 'boundary': 'Current protocol cash and supply headroom, not a reserved allocation. Core cap zero means no supply. Stored borrow totals may lag accrued interest; headroom is preliminary. Individual collateral constraints and transfer fees still apply.'}


def health_scenarios(observation: dict[str, Any], target: float, drop_pct: float, rise_pct: float) -> dict[str, Any]:
    debt = D(observation['debt_usd'])
    weighted = D(observation['weighted_collateral_usd'])
    stressed_c = weighted*(1-D(str(drop_pct))/100)
    stressed_d = debt*(1+D(str(rise_pct))/100)
    repay = max(D(0), stressed_d-stressed_c/D(str(target))).quantize(D('.01'), rounding=ROUND_CEILING)
    return {'current_health_factor': observation['health_factor'],
            'stressed_health_factor': str(stressed_c/stressed_d) if stressed_d else None,
            'required_external_repay_usd': str(min(repay, stressed_d)),
            'target': target, 'collateral_drop_pct': drop_pct, 'debt_price_rise_pct': rise_pct,
            'assumptions': 'Uniform caller-selected price shocks; externally funded repayment. No probability or guarantee.'}


def draft(to: str, signature: str, types: list[str], args: list[Any], sender: str, label: str) -> dict[str, Any]:
    return {'label': label, 'chain_id': 56, 'from': sender, 'to': to,
            'data': calldata(signature, types, args), 'value': '0x0', 'ready_to_send': False,
            'requires': ['Wallet owner consent', 'Fresh simulation after prerequisites', 'Explicit wallet signature']}


async def prepare_action(row: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
    kind, spec = row['kind'], row['spec']
    result: dict[str, Any] = {'schema': 'safehire-action-preparation/1', 'kind': kind,
                              'prepared_at': utcnow().isoformat(), 'assumptions': {'task_inputs':spec,'action_options':options},
                              'trade_executed': False, 'wallet_authorized': False,
                              'ready_to_send': False, 'drafts': [], 'blockers': [], 'steps': []}
    if kind == 'yield':
        obs = await observe_venus()
        capacity = await venus_capacity(obs)
        comparison = yield_comparison(obs, spec)
        target = comparison['best_under_assumptions']
        current = next(r for r in capacity['markets'] if r['venue_id'] == spec['current_venue'])
        destination = next(r for r in capacity['markets'] if r['venue_id'] == target)
        amount = D(str(spec['capital']))
        blockers = ['The actual withdrawable balance and wallet balance are not verified.', 'Stablecoin swap quotes, complete costs and approvals are not available.']
        if current['redeem_paused'] or D(current['cash_token_units']) < amount:
            blockers.append('The source venue pauses withdrawals or has less cash than the assumed amount.')
        if target != spec['current_venue'] and (destination['mint_paused'] or D(destination['supply_room_token_units']) < amount):
            blockers.append('The destination pauses deposits or has less capacity than the assumed amount.')
        best = next(r for r in comparison['alternatives'] if r['venue'] == target)
        gross_edge = D(best['increment_vs_hold_usd']) + (D(str(spec['cost'])) if target != spec['current_venue'] else 0)
        result.update(observation=obs, capacity=capacity, metrics=comparison, blockers=blockers,
                      summary='Staying in the current venue is preferable under these assumptions.' if target == spec['current_venue'] else 'A yield candidate was found. Actual exit and swap conditions still need review.',
                      break_even_days_linear_estimate=str(D(str(spec['cost']))/(gross_edge/D(str(spec['days'])))) if gross_edge > 0 else None,
                      steps=['Check your withdrawable balance and collateral restrictions.', 'Obtain actual swap quotes and total costs.', 'Compare again with staying in the current venue.', 'Personally confirm withdrawal, swap and deposit.', 'Read before/after balances and verify receipts.'])
    elif kind == 'health':
        obs = await observe_health(spec['account'])
        result.update(observation=obs, metrics=health_scenarios(obs, spec['target'], options['collateral_drop_pct'], options['debt_rise_pct']),
                      summary='Stress scenario and repayment conditions prepared.',
                      steps=['Confirm you can operate this account.', 'Select the actual debt asset and external repayment amount.', 'Check the balance and exact allowance.', 'Personally sign the repayment.', 'Read the health factor again; transaction success alone is insufficient.'])
        if options.get('amount') is not None:
            amount_raw = token_amount(options['amount'])
            venue = options['venue']
            calls = BlockCalls(obs)
            controller, underlying, decimals, debt, balance, allowance, paused, all_paused = await asyncio.gather(
                calls.call(MARKETS[venue], 'comptroller()', ['address']),
                calls.call(MARKETS[venue], 'underlying()', ['address']),
                calls.call(UNDERLYINGS[venue], 'decimals()', ['uint8']),
                calls.call(MARKETS[venue], 'borrowBalanceCurrent(address)', ['uint256'], ['address'], [spec['account']]),
                calls.call(UNDERLYINGS[venue], 'balanceOf(address)', ['uint256'], ['address'], [spec['account']]),
                calls.call(UNDERLYINGS[venue], 'allowance(address,address)', ['uint256'], ['address','address'], [spec['account'], MARKETS[venue]]),
                calls.call(COMPTROLLER, 'actionPaused(address,uint8)', ['bool'], ['address','uint8'], [MARKETS[venue], 3]),
                calls.call(COMPTROLLER, 'protocolPaused()', ['bool']))
            if controller[0].lower() != COMPTROLLER or underlying[0].lower() != UNDERLYINGS[venue] or decimals[0] != 18:
                raise ValueError('Repayment market identity changed')
            blockers = []
            if amount_raw > debt[0]: blockers.append('The proposed amount exceeds the current debt in this market.')
            if amount_raw > balance[0]: blockers.append('The wallet has insufficient tokens for this repayment.')
            if paused[0] or all_paused[0]: blockers.append('Repayment is currently paused by the protocol.')
            repayment = draft(MARKETS[venue], 'repayBorrow(uint256)', ['uint256'], [amount_raw], spec['account'], 'Repay your debt in the specified Venus market.')
            drafts = []
            if allowance[0] != amount_raw:
                if allowance[0]:
                    drafts.append(draft(UNDERLYINGS[venue], 'approve(address,uint256)', ['address','uint256'], [MARKETS[venue],0], spec['account'], 'Clear the existing allowance first.'))
                drafts.append(draft(UNDERLYINGS[venue], 'approve(address,uint256)', ['address','uint256'], [MARKETS[venue],amount_raw], spec['account'], 'Approve only this repayment amount.'))
                blockers.append('Confirm the exact allowance before simulating repayment.')
            elif not blockers:
                code = (await calls.call(MARKETS[venue], 'repayBorrow(uint256)', ['uint256'], ['uint256'], [amount_raw], spec['account']))[0]
                result['simulation'] = {'method': 'eth_call', 'protocol_return_code': code, 'passed': code == 0, 'transaction_sent': False}
                if code: blockers.append('Venus returned a repayment error code. This is not a successful simulation.')
            drafts.append(repayment)
            await calls.finish()
            result.update(drafts=drafts, blockers=blockers, preflight_reads=calls.reads,
                          selected_debt_raw=str(debt[0]), available_token_raw=str(balance[0]))
        else:
            result['blockers'] = ['Select an actual debt token and amount before preparing a repayment draft.']
    elif kind == 'lp':
        obs = await observe_lp(spec['position_id'])
        lower, upper = lp_range({'current_tick': obs['current_tick'], 'tick_spacing': obs['tick_spacing'], 'half_width_ticks': options['half_width_ticks']})
        def inventory(lo: int, hi: int) -> dict[str, str]:
            return lp_inventory(obs['current_tick'], lo, hi, int(obs['liquidity_raw']), 18, 18)
        old, new = inventory(obs['lower_tick'], obs['upper_tick']), inventory(lower, upper)
        result.update(observation=obs, summary='The position is in range. First assess whether adjustment is worthwhile.' if obs['in_range'] else 'The position is out of range. Review conditions before adjusting.',
                      metrics={'old_inventory': old, 'new_inventory_same_liquidity': new, 'target_lower_tick': lower, 'target_upper_tick': upper,
                               'inventory_delta': {t: str(D(new[t])-D(old[t])) for t in ['token0','token1']}},
                      blockers=['After withdrawal, obtain swap and new-position quotes using the actual received assets.', 'Wallet-owner confirmation and costs for the complete operation are not verified.'],
                      steps=['Review the current position and target range.', 'Simulate withdrawing and collecting to the original owner.', 'Obtain swap and new-position quotes using actual received balances.', 'Personally confirm exact allowances and the new position.', 'Check the new position, remaining assets and fees.'])
        if options['simulate_lp_exit']:
            calls = BlockCalls(obs)
            deadline = int(utcnow().timestamp()) + 600
            params = '(uint256,uint128,uint256,uint256,uint256)'
            args = [obs['position_id'], int(obs['liquidity_raw']), 0, 0, deadline]
            # Zero-minimum call is a non-broadcast quote only. Export only protected calldata.
            amounts = await calls.call(MANAGER, 'decreaseLiquidity('+params+')', ['uint256','uint256'], [params], [tuple(args)], obs['owner'])
            args[2:4] = [a*(10000-options['slippage_bps'])//10000 for a in amounts]
            if any(a > 0 and m == 0 for a, m in zip(amounts, args[2:4])):
                raise ValueError('Dust withdrawal cannot have a protected minimum')
            decrease = calldata('decreaseLiquidity('+params+')', [params], [tuple(args)])
            collect_type = '(uint256,address,uint128,uint128)'
            collect = calldata('collect('+collect_type+')', [collect_type], [(obs['position_id'],obs['owner'],2**128-1,2**128-1)])
            batch = [bytes.fromhex(decrease[2:]), bytes.fromhex(collect[2:])]
            returned = await calls.call(MANAGER, 'multicall(bytes[])', ['bytes[]'], ['bytes[]'], [batch], obs['owner'])
            if len(returned[0]) != 2:
                raise ValueError('Unexpected LP exit simulation')
            removed = decode(['uint256','uint256'], returned[0][0])
            received = decode(['uint256','uint256'], returned[0][1])
            if any(a < m or c < a for a, m, c in zip(removed, args[2:4], received)):
                raise ValueError('LP simulated amounts violate withdrawal minima')
            await calls.finish()
            result.update(drafts=[draft(MANAGER,'multicall(bytes[])',['bytes[]'],[batch],obs['owner'],'Withdraw the original liquidity and collect to its owner. This does not create a new position.')],
                          simulation={'passed': True, 'method': 'eth_call', 'deadline': deadline,
                                      'principal_minimum_raw': [str(a) for a in args[2:4]], 'collect_raw': [str(a) for a in received],
                                      'transaction_sent': False}, preflight_reads=calls.reads)
    elif kind == 'grid':
        obs = await observe_grid_market()
        metrics = grid_metrics({'lower_price':spec['lower'], 'upper_price':spec['upper'], 'levels':options['levels'],
                                'capital_usd':options['capital'], 'fee_bps_per_side':5,
                                'transfer_tax_bps_per_side':options['transfer_tax_bps'], 'slippage_bps_per_side':options['slippage_bps'],
                                'gas_usd_per_order':options['gas_per_order']})
        result.update(observation=obs, metrics=metrics, summary='One modeled cycle cannot cover assumed costs. Stop this plan.' if metrics['net_adjacent_cycle_usd'] <= 0 else 'One modeled cycle is positive. Actual execution feasibility remains unproven.',
                      fee_source='Reviewed fixed PancakeSwap pool fee 500 / 1e6 = 5 bps per swap',
                      plan_levels=[{'index':i+1, 'price_usdt':p, 'allocated_usd':metrics['capital_per_level_usd'], 'state':'unsubmitted_plan'} for i,p in enumerate(metrics['prices'])],
                      blockers=['No reviewed automatic grid execution service is connected.', 'Actual quotes, wallet inventory and network costs still require review.'],
                      steps=['Check the reference market price and range.', 'Check each level amount and fees on both sides.', 'Obtain actual order quotes and execution approval.', 'Track actual fills and inventory.', 'Stop new orders outside the range. Cancelling existing orders requires an execution service.'])
    else:
        raise ValueError('Use the order recovery action for paid jobs')
    result['boundary'] = 'Fresh public observations plus explicit caller assumptions. Drafts are not signed, broadcast, complete strategy execution, or profit evidence. Re-read after any prerequisite; drafts expire with the snapshot.'
    result['valid_until'] = int(utcnow().timestamp()) + 60
    return result | {'plan_hash': digest(result)}


def token_amount(amount: str) -> int:
    value = D(amount)
    scaled = value*10**18
    if not value.is_finite() or not 0 < value <= 1_000_000 or scaled != scaled.to_integral_value():
        raise ValueError('Token amount must be positive, at most 1000000, and at most 18 decimals')
    return int(scaled)
