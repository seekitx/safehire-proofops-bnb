"""Explicit conversion of public observations into calculator inputs."""
from __future__ import annotations

from typing import Any

from proofops.arena.financial_sources import observe_venus
from proofops.arena.health_sources import observe_health
from proofops.services.reviewed_calculators import inputs


async def prepare(token: int, account: str | None, capital: float) -> dict[str, Any]:
    if token == 269228:
        if not account:
            raise ValueError('请输入要检查的公开 Venus Core 账户地址')
        observation = await observe_health(account)
        collateral = {}; debt = {}; prices = {}
        for index, market in enumerate(observation['markets']):
            name = f'market_{index}_USD'
            supplied = float(market['supplied_usd']); borrowed = float(market['borrowed_usd'])
            threshold = float(market['liquidation_threshold'])
            if supplied > 0 and threshold > 0:
                collateral[name] = {'amount': supplied, 'liqThreshold': threshold}
                prices[name] = 1
            if borrowed > 0:
                debt[name] = borrowed
                prices[name] = 1
        if not debt or not collateral:
            raise ValueError('该账户没有可比较的抵押与债务；不要为不适用的计算付款')
        task = inputs(token, {'collateral': collateral, 'debt': debt, 'prices': prices})
        boundary = '各市场转换为美元计价份额，单价 1 仅用于复算健康系数；不是代币真实单价，不能把供应商逐资产清算价格当作代币卖出价。快照之后价格、利息和参数可能变化。'
    else:
        observation = await observe_venus()
        task = inputs(token, {'pools': {r['venue_id']: {'apyPct': float(r['projected_supply_apy_pct'])}
                                       for r in observation['markets']}, 'capitalUsd': capital, 'maxPerPoolPct': 60})
        boundary = '只读取 Venus Core USDT/USDC 当前利率。资金和 60% 集中度上限是你的假设；未取得容量或独立风险评分，未传入 TVL，供应商默认风险分不是事实认证。未计迁移费用、退出限制、奖励与脱锚风险。'
    return {'task_input': task, 'observation': observation, 'boundary': boundary,
            'scope': 'point_in_time_calculation', 'paid': False, 'trade_executed': False}
