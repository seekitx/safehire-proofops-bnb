from __future__ import annotations

import copy
import math
from datetime import timedelta

import pytest
from pydantic import ValidationError

from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec
from proofops.arena.planners import (
    compare,
    evaluate,
    grid_metrics,
    health_metrics,
    lp_inventory,
    reference_proposal,
    yield_metrics,
)

CATEGORIES = list(examples()['tasks'])


def spec(category='rebalancing'):
    return TaskSpec.model_validate(examples()['tasks'][category])


@pytest.mark.parametrize('category', CATEGORIES)
def test_reference_is_valid_but_not_chain_truth(category):
    task = spec(category)
    result = evaluate(task, reference_proposal(task))
    assert result['policy_accepted']
    assert result['evidence_mode'] == 'caller_supplied_model_validation'
    assert not result['trade_executed'] and not result['chain_snapshot_verified']
    assert not result['agent_authorship_verified']


@pytest.mark.parametrize('category', CATEGORIES)
def test_snapshot_expiration_blocks_all_categories(category):
    task = spec(category)
    result = evaluate(task, reference_proposal(task), now=task.snapshot.observed_at + timedelta(seconds=301))
    assert not result['policy_accepted']
    assert not next(c for c in result['checks'] if c['name']=='fresh_snapshot')['passed']


@pytest.mark.parametrize('category', CATEGORIES)
def test_proposal_task_and_snapshot_substitution_blocked(category):
    task = spec(category)
    p = reference_proposal(task).model_copy(update={'task_hash':'a'*64, 'snapshot_hash':'b'*64})
    r=evaluate(task,p)
    assert not r['policy_accepted']
    assert {'same_task','same_snapshot'} <= {c['name'] for c in r['checks'] if not c['passed']}


@pytest.mark.parametrize('category', CATEGORIES)
def test_input_change_changes_binding(category):
    task=spec(category)
    changed=task.to_dict(); changed['limits']['max_cost_usd']=9
    newer=TaskSpec.model_validate(changed)
    assert newer.task_hash != task.task_hash
    assert not evaluate(newer,reference_proposal(task))['policy_accepted']


@pytest.mark.parametrize('value', [True,False,float('nan'),float('inf'),-1,1e30])
def test_bad_financial_values_rejected(value):
    task=spec('grid_trading').to_dict();task['inputs']['capital_usd']=value
    with pytest.raises(ValidationError):TaskSpec.model_validate(task)


@pytest.mark.parametrize('key', ['chain_id','block_number'])
def test_boolean_chain_fields_rejected(key):
    task=spec().to_dict(); task['snapshot'][key]=True
    with pytest.raises(ValidationError):TaskSpec.model_validate(task)


def test_timezone_and_unknown_fields_rejected():
    raw=spec().to_dict();raw['snapshot']['observed_at']='2026-09-06T12:00:00'
    with pytest.raises(ValidationError):TaskSpec.model_validate(raw)
    raw=spec().to_dict();raw['inputs']['profit_guaranteed']=100
    with pytest.raises(ValidationError):TaskSpec.model_validate(raw)


def test_lp_tick_alignment_and_inventory():
    task=spec(); p=reference_proposal(task)
    assert p.parameters == {'lower_tick':120,'upper_tick':480}
    p=p.model_copy(update={'parameters':{'lower_tick':121,'upper_tick':480}})
    assert not evaluate(task,p)['policy_accepted']
    low=lp_inventory(-300,-120,120,10**18,18,18)
    high=lp_inventory(300,-120,120,10**18,18,18)
    assert float(low['token0'])>0 and float(low['token1'])==0
    assert float(high['token0'])==0 and float(high['token1'])>0


def test_lp_decimals_and_no_automatic_rebalance_inside_range():
    a=lp_inventory(0,-120,120,10**18,18,18)
    b=lp_inventory(0,-120,120,10**18,6,18)
    assert math.isclose(float(b['token0'])/float(a['token0']),1e12)
    raw=spec().to_dict();raw['inputs']['current_tick']=0
    task=TaskSpec.model_validate(raw)
    assert reference_proposal(task).action=='hold'
    p=reference_proposal(task).model_copy(update={'action':'reset_lp_range','parameters':{'lower_tick':-180,'upper_tick':180}})
    assert not evaluate(task,p)['policy_accepted']


@pytest.mark.parametrize('params',[{'lower_tick':True,'upper_tick':480},{'lower_tick':-900000,'upper_tick':480},{'lower_tick':480,'upper_tick':120},{'lower_tick':120,'upper_tick':480,'approved':True}])
def test_lp_adversarial_outputs_blocked(params):
    task=spec();p=reference_proposal(task).model_copy(update={'parameters':params})
    assert not evaluate(task,p)['policy_accepted']


def test_grid_costs_can_reverse_a_profitable_gross_spread():
    raw=spec('grid_trading').to_dict();raw['inputs']['fee_bps_per_side']=200
    task=TaskSpec.model_validate(raw)
    m=grid_metrics(task.inputs)
    assert m['net_adjacent_cycle_usd'] < 0
    assert reference_proposal(task).action=='hold'
    assert evaluate(task,reference_proposal(task))['policy_accepted']


@pytest.mark.parametrize('field', ['fee_bps_per_side','transfer_tax_bps_per_side','slippage_bps_per_side','gas_usd_per_order'])
def test_grid_higher_costs_never_improve_cycle(field):
    i=spec('grid_trading').inputs
    before=grid_metrics(i)['net_adjacent_cycle_usd']
    i=copy.deepcopy(i);i[field]+=1
    assert grid_metrics(i)['net_adjacent_cycle_usd'] < before


def test_grid_prices_missing_extra_or_stop_bypassed():
    task=spec('grid_trading');p=reference_proposal(task)
    for params in ({'prices':p.parameters['prices'][:-1],'stop_price':85},
                   {'prices':p.parameters['prices'],'stop_price':0},
                   {'prices':[True]*8,'stop_price':85}):
        assert not evaluate(task,p.model_copy(update={'parameters':params}))['policy_accepted']


def test_yield_compares_against_hold_and_rejects_capacity_and_exit():
    task=spec('yield_optimisation');rows=yield_metrics(task.inputs)
    good=next(r for r in rows if r['venue_id']=='scenario-venue-a')
    expected=1000*((1.08)**(90/365)-(1.05)**(90/365))-1
    assert math.isclose(good['improvement_vs_hold_usd'],expected,abs_tol=1e-10)
    raw=task.to_dict();raw['inputs']['venues'][0]['capacity_usd']=10
    task=TaskSpec.model_validate(raw);assert reference_proposal(task).action=='hold'
    raw=spec('yield_optimisation').to_dict();raw['inputs']['venues'][0]['withdrawal_delay_days']=91
    task=TaskSpec.model_validate(raw);assert reference_proposal(task).action=='hold'


def test_yield_higher_apy_with_high_cost_is_not_best():
    task=spec('yield_optimisation')
    assert reference_proposal(task).parameters['venue_id']=='scenario-venue-a'
    bad=reference_proposal(task).model_copy(update={'parameters':{'venue_id':'scenario-venue-b'}})
    assert not evaluate(task,bad)['policy_accepted']


def test_duplicate_venues_rejected():
    raw=spec('yield_optimisation').to_dict();raw['inputs']['venues'].append(raw['inputs']['venues'][0])
    with pytest.raises(ValidationError):TaskSpec.model_validate(raw)


def test_health_repay_ceiling_and_insufficient_budget():
    task=spec('health_factor_monitoring');m=health_metrics(task.inputs)
    assert m['required_repay_usd']==173.34
    p=reference_proposal(task)
    assert evaluate(task,p)['metrics']['modeled_health_after'] >= 1.5
    p=p.model_copy(update={'parameters':{'repay_usd':173.33}})
    assert not evaluate(task,p)['policy_accepted']
    raw=task.to_dict();raw['inputs']['available_repay_usd']=100
    task=TaskSpec.model_validate(raw)
    assert reference_proposal(task).action=='hold'
    assert not evaluate(task,reference_proposal(task))['policy_accepted']


def test_health_debt_appreciation_and_collateral_shock_worsen_repay():
    i=spec('health_factor_monitoring').inputs
    baseline=health_metrics(i)['required_repay_usd']
    i=copy.deepcopy(i);i['debts'][0]['price_rise_pct']=10
    assert health_metrics(i)['required_repay_usd']>baseline
    i['collateral'][0]['price_drop_pct']=30
    assert health_metrics(i)['required_repay_usd']>baseline


def test_zero_debt_has_no_fake_infinite_json_number():
    raw=spec('health_factor_monitoring').to_dict();raw['inputs']['debts'][0]['value_usd']=0
    task=TaskSpec.model_validate(raw);p=reference_proposal(task)
    r=evaluate(task,p)
    assert p.action=='hold' and r['policy_accepted']
    assert r['metrics']['no_debt'] and r['metrics']['health_factor_now'] is None


def test_same_agent_comparison_and_different_task_fail_closed():
    task=spec();p=reference_proposal(task)
    with pytest.raises(ValueError):compare(task,[p,p])
    other=p.model_copy(update={'agent_ref':'local:challenger','task_hash':'0'*64})
    r=compare(task,[p,other]);assert len(r['eligible_agent_refs'])==1 and r['winner'] is None


@pytest.mark.parametrize('category', list(examples()['tasks']))
def test_guided_walkthrough_has_one_pass_one_fail_but_zero_real_providers(category):
    from proofops.arena.examples import walkthrough
    result = walkthrough(category)
    assert [r['policy_accepted'] for r in result['comparison']['reports']] == [True, False]
    assert result['real_provider_count'] == 0
    assert not result['public_reputation_updated'] and not result['funds_moved']


def test_lp_budget_limited_hold_is_not_claimed_as_completed_range_protection():
    from proofops.arena.models import TaskSpec
    spec = examples()['tasks']['rebalancing']
    spec['limits']['max_cost_usd'] = 0
    task = TaskSpec.model_validate(spec)
    proposal = reference_proposal(task)
    assert proposal.action == 'hold'
    report = evaluate(task, proposal)
    assert not report['policy_accepted']
    assert any(c['name'] == 'range_target_resolved' and not c['passed'] for c in report['checks'])
