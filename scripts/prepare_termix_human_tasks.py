"""Freeze real observations for human comparisons; never generates human answers."""
from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from proofops.arena.financial_sources import observe_venus
from proofops.arena.health_sources import observe_health
from proofops.arena.lp_sources import observe_lp

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'live-20260908'


def save(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


async def main() -> None:
    paths = [ROOT / f'evidence/termix/tasks/{PREFIX}-{kind}.json' for kind in ('health', 'grid', 'yield')]
    if any(path.exists() for path in paths):
        raise ValueError('Frozen tasks already exist; do not replace inputs after an experiment starts')
    health, lp, venus = await asyncio.gather(
        observe_health('0xd319e1F8e987cf78333cEA853F455366640929cF'),
        observe_lp(7319347), observe_venus(),
    )
    # Aggregate the same-block liquidation thresholds using observed collateral weights.
    factor = Decimal(health['weighted_collateral_usd']) / Decimal(health['collateral_usd'])
    price = float(Decimal('1.0001') ** -lp['current_tick'])
    common = '这是同一时间保存的数据对照，不是现在的交易指令。可用普通计算器或表格，不使用任何 AI 或市场代理。写出计算过程、结论和限制；不要转账。'
    tasks: list[tuple[str, dict[str, Any], str, dict[str, Any], str, str]] = [
        ('health', health, 'hf-shield-demo', {
            'collateral_usd': float(health['collateral_usd']), 'debt_usd': float(health['debt_usd']),
            'liquidation_threshold': float(factor), 'alert_health_factor': 1.25, 'target_health_factor': 1.5,
        }, '借贷账户检查',
         ('用下面的真实公开借贷账户数据，判断是否触发 1.25 的提醒线，并计算达到 1.5 目标需要偿还多少美元。\n'
         '公式：健康系数 = 抵押品美元价值 × 加权清算阈值 ÷ 债务美元价值。\n'
         '目标允许债务 = 抵押品美元价值 × 加权清算阈值 ÷ 1.5。需偿还 = 债务 − 目标允许债务；小于零时填零。\n'
         '健康系数小于 1.25 时提醒，否则继续观察。说明为什么这一结果不能保证以后不会被清算。账户不是你的钱包。')),
        ('grid', lp, 'grid-sentinel-demo', {
            'current_price': price, 'lower_price': price * .95, 'upper_price': price * 1.05,
            'levels': 9, 'capital_usd': 1000, 'max_drawdown_pct': 5,
        }, '网格价格计划',
         ('根据真实池子价格，计算上下界之间的 9 档等比价格，以及每档分配多少美元。\n'
         '公式：第 i 档价格 = 下界 × (上界 ÷ 下界)^(i ÷ 8)，i 从 0 到 8。每档资金 = 总资金 ÷ 9。\n'
         '列出 9 档价格（保留两位小数即可），写明设置的最大回撤比例是否已经自动执行，以及真正下单前还缺什么。\n'
         '资金 1000 美元、上下 5% 和 9 档是任务设定；USDT 按 1 美元估算。手续费、滑点和燃料费未知，不计算净利润。')),
        ('yield', venus, 'yield-scout-demo', {
            'capital_usd': 10000, 'horizon_days': 30,
            'candidates': [{'protocol': row['venue_id'], 'gross_apy': float(row['projected_supply_apy_pct']),
                            'risk_score': risk, 'tvl_usd': 0, 'transaction_cost_usd': .09}
                           for row, risk in zip(venus['markets'], (22, 18), strict=True)],
        }, '两种存款收益比较',
         ('用真实读取的两种 Venus 利率，比较 10000 美元放置 30 天的预计净收益和扣除风险分后的排序。\n'
         'APY 是按当前利率推算的年收益率（百分数），不是保证收益。\n'
         '公式：净收益 = 10000 × [(1 + APY ÷ 100)^(30 ÷ 365) − 1] − 0.09。\n'
         '扣分后收益 = 净收益 − |净收益| × 风险分 ÷ 125。对两种市场分别计算，按扣分后收益从大到小排序。\n'
         '风险分 22 / 18、成本 0.09 美元、资金和期限是任务假设。TVL（存款总规模）未读取，接口中的 0 仅表示未知，不能写成实际规模为零。\n'
         '说明为什么不能仅凭本次估算就直接存款或保证获利。')),
    ]
    for kind, observation, agent, inputs, title, brief in tasks:
        task_id = f'{PREFIX}-{kind}'
        source_path = f'evidence/termix/sources/{task_id}.json'
        save(ROOT / source_path, observation)
        inputs['source'] = f"recorded_bsc_block_{observation['block_number']}_with_disclosed_task_assumptions"
        task = {'schema_version': 'safehire-termix-task/2', 'task_id': task_id,
                'title_zh': title, 'manual_brief_zh': common + '\n\n' + brief,
                'source_snapshot': {'path': source_path, 'observation_hash': observation['observation_hash'],
                                    'block_number': observation['block_number'], 'observed_at': observation['observed_at']},
                'agent_request': {'skill': 'hire_analysis', 'task_id': task_id, 'agent_id': agent, 'input': inputs},
                'comparison_rule': 'Identical frozen inputs and formulas; manual participant uses no AI. Time includes reading, calculation and writing. Agent transport timing excludes shared source collection; record this limitation.',
                'boundary': 'Real recorded chain data plus declared hypothetical capital/targets. Sponsored first-party analysis, not a paid independent provider or executed strategy.'}
        save(ROOT / f'evidence/termix/tasks/{task_id}.json', task)
        print(task_id, observation['block_number'])


if __name__ == '__main__':
    asyncio.run(main())
