from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

Category = Literal['rebalancing', 'grid_trading', 'yield_optimisation', 'health_factor_monitoring']
Action = Literal['hold', 'reset_lp_range', 'plan_grid', 'route_yield', 'repay']
Nonnegative = Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, le=1e12, allow_inf_nan=False)]
Pct = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


def canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def utcnow() -> datetime:
    return datetime.now(UTC)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, validate_default=True)

    @model_validator(mode='before')
    @classmethod
    def reject_boolean_numbers(cls, value: Any) -> Any:
        # JSON booleans must never become financial values (True == 1 in Python).
        if isinstance(value, dict):
            for key, item in value.items():
                if isinstance(item, bool) and key in cls.model_fields:
                    field = cls.model_fields[key]
                    if field.annotation is not bool:
                        raise ValueError(f'{key}: boolean is not a number or string')
        return value


class Snapshot(StrictModel):
    chain_id: Literal[56] = 56
    block_number: Annotated[StrictInt, Field(gt=0)]
    block_hash: str = Field(pattern=r'^0x[0-9a-fA-F]{64}$')
    observed_at: datetime
    source: str = Field(min_length=1, max_length=200)

    @field_validator('observed_at')
    @classmethod
    def aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError('snapshot requires a timezone-aware timestamp')
        return value.astimezone(UTC)


class Limits(StrictModel):
    max_cost_usd: Nonnegative = 10
    max_slippage_bps: Annotated[StrictInt, Field(ge=0, le=500)] = 100
    max_snapshot_age_seconds: Annotated[StrictInt, Field(ge=10, le=3600)] = 300


class LPInput(StrictModel):
    current_tick: Annotated[StrictInt, Field(ge=-887000, le=887000)]
    old_lower_tick: Annotated[StrictInt, Field(ge=-887272, le=887272)]
    old_upper_tick: Annotated[StrictInt, Field(ge=-887272, le=887272)]
    tick_spacing: Annotated[StrictInt, Field(ge=1, le=1000)]
    half_width_ticks: Annotated[StrictInt, Field(ge=1, le=100000)]
    liquidity_raw: Annotated[StrictInt, Field(gt=0, le=2**128 - 1)]
    token0_decimals: Annotated[StrictInt, Field(ge=0, le=36)] = 18
    token1_decimals: Annotated[StrictInt, Field(ge=0, le=36)] = 18
    estimated_cost_usd: Nonnegative
    slippage_bps: Annotated[StrictInt, Field(ge=0, le=500)] = 50

    @model_validator(mode='after')
    def ranges(self) -> LPInput:
        if not self.old_lower_tick < self.old_upper_tick:
            raise ValueError('old LP range must have positive width')
        if self.old_lower_tick % self.tick_spacing or self.old_upper_tick % self.tick_spacing:
            raise ValueError('old LP ticks must align to tick spacing')
        if self.half_width_ticks < self.tick_spacing:
            raise ValueError('requested half width must be at least one tick spacing')
        return self


class GridInput(StrictModel):
    current_price: Positive
    lower_price: Positive
    upper_price: Positive
    levels: Annotated[StrictInt, Field(ge=2, le=50)] = 10
    capital_usd: Positive
    fee_bps_per_side: Nonnegative
    transfer_tax_bps_per_side: Nonnegative = 0
    slippage_bps_per_side: Annotated[StrictInt, Field(ge=0, le=500)] = 30
    gas_usd_per_order: Nonnegative
    stop_price: Positive

    @model_validator(mode='after')
    def bounds(self) -> GridInput:
        if not self.stop_price < self.lower_price < self.current_price < self.upper_price:
            raise ValueError('require stop < lower < current < upper')
        if self.fee_bps_per_side + self.transfer_tax_bps_per_side + self.slippage_bps_per_side >= 5000:
            raise ValueError('per-side modeled costs must be below 50%')
        if self.upper_price / self.lower_price > 1e6:
            raise ValueError('grid price ratio exceeds supported limit')
        return self


class Venue(StrictModel):
    venue_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    apy_pct: Annotated[float, Field(ge=0, le=1000)]
    migration_cost_usd: Nonnegative
    capacity_usd: Nonnegative
    withdrawal_delay_days: Annotated[StrictInt, Field(ge=0, le=365)] = 0


class YieldInput(StrictModel):
    capital_usd: Positive
    current_apy_pct: Annotated[float, Field(ge=0, le=1000)]
    horizon_days: Annotated[StrictInt, Field(ge=1, le=365)]
    min_improvement_usd: Nonnegative = 0
    venues: list[Venue] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def unique(self) -> YieldInput:
        if len({v.venue_id for v in self.venues}) != len(self.venues):
            raise ValueError('venue IDs must be unique')
        return self


class Collateral(StrictModel):
    asset: str = Field(min_length=1, max_length=32)
    value_usd: Nonnegative
    liquidation_threshold: Annotated[float, Field(gt=0, le=1)]
    price_drop_pct: Annotated[float, Field(ge=0, lt=100)]


class Debt(StrictModel):
    asset: str = Field(min_length=1, max_length=32)
    value_usd: Nonnegative
    price_rise_pct: Annotated[float, Field(ge=0, le=500)] = 0


class HealthInput(StrictModel):
    collateral: list[Collateral] = Field(min_length=1, max_length=30)
    debts: list[Debt] = Field(min_length=1, max_length=30)
    target_health_factor: Annotated[float, Field(gt=1, le=10)] = 1.5
    available_repay_usd: Nonnegative
    estimated_cost_usd: Nonnegative

    @model_validator(mode='after')
    def unique(self) -> HealthInput:
        for values in (self.collateral, self.debts):
            if len({v.asset for v in values}) != len(values):
                raise ValueError('duplicate assets are not allowed within a side')
        return self


INPUT_MODELS: dict[Category, type[StrictModel]] = {
    'rebalancing': LPInput,
    'grid_trading': GridInput,
    'yield_optimisation': YieldInput,
    'health_factor_monitoring': HealthInput,
}


class TaskSpec(StrictModel):
    schema_version: Literal['safehire-task/2'] = 'safehire-task/2'
    category: Category
    snapshot: Snapshot
    limits: Limits = Field(default_factory=Limits)
    inputs: dict[str, Any]

    @model_validator(mode='after')
    def normalize_inputs(self) -> TaskSpec:
        self.inputs = INPUT_MODELS[self.category].model_validate(self.inputs).model_dump(mode='json')
        if len(canonical(self.inputs).encode()) > 24000:
            raise ValueError('task inputs exceed 24 KiB')
        return self

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode='json')

    @property
    def task_hash(self) -> str:
        return digest({'domain': 'safehire-acceptance-task-v2', 'task': self.to_dict()})

    @property
    def snapshot_hash(self) -> str:
        return digest(self.snapshot.model_dump(mode='json'))

    def fresh(self, now: datetime | None = None) -> bool:
        age = ((now or utcnow()) - self.snapshot.observed_at).total_seconds()
        return -5 <= age <= self.limits.max_snapshot_age_seconds


class Proposal(StrictModel):
    schema_version: Literal['safehire-proposal/2'] = 'safehire-proposal/2'
    agent_ref: str = Field(pattern=r'^(local:[a-zA-Z0-9_-]{1,64}|56:[1-9][0-9]{0,77}:[a-zA-Z0-9_-]{1,64})$')
    task_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    snapshot_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    action: Action
    parameters: dict[str, Any]

    @model_validator(mode='after')
    def finite_parameters(self) -> Proposal:
        if len(canonical(self.parameters).encode()) > 16000:
            raise ValueError('proposal parameters exceed 16 KiB')
        return self

    @property
    def proposal_hash(self) -> str:
        return digest(self.model_dump(mode='json'))
