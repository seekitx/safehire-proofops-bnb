import asyncio
import copy
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from proofops.services import live_erc8183, reviewed_grid
from proofops.workspace import worker
from proofops.workspace.routes import make_router
from proofops.workspace.store import Journal

ROOT = Path(__file__).resolve().parents[1]


def delivered():
    return json.loads((ROOT/'evidence/marketplace/chainhelix-56741/delivery.raw.json').read_text())


def test_actual_grid_delivery_and_wrong_task_are_distinguished():
    content = delivered()['response']['content']
    task = {'price':750, 'budgetUsd':1000, 'levels':5, 'spanPct':2}
    assert reviewed_grid.acceptance(task, content)['passed']
    assert not reviewed_grid.acceptance(task | {'price':751}, content)['passed']
    for key, value in [('allocatedUsd', 999), ('mark', 0), ('ok', False)]:
        result = json.loads(content)
        result[key] = value
        assert not reviewed_grid.acceptance(task, json.dumps(result))['passed']
    result = json.loads(content)
    result['buys'][0]['amount'] = 100
    assert not reviewed_grid.acceptance(task, json.dumps(result))['passed']


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), True, 0, -1, '750'])
def test_grid_rejects_invalid_price_before_negotiation(bad):
    with pytest.raises(ValueError):
        reviewed_grid.inputs({'price':bad, 'budgetUsd':1000})


def test_flat_task_only_accepted_for_reviewed_provider():
    v = json.loads((ROOT/'evidence/marketplace/chainhelix-56741/verification.json').read_text())
    assert live_erc8183._parse_task_spec(v['description'], provider=reviewed_grid.WALLET)['erc8004_token_id'] == 269224
    with pytest.raises(ValueError):
        live_erc8183._parse_task_spec(v['description'], provider='0x'+'11'*20)


def test_durable_claim_pause_and_expiry(tmp_path):
    journal = Journal(tmp_path/'work.sqlite')
    space = journal.create_space()
    identifier = journal.add(space['space_id'], 'health', {'account':'0x'+'11'*20}, now=100)
    assert journal.add(space['space_id'], 'health', {'account':'0x'+'11'*20}, now=101) == identifier
    restored = Journal(tmp_path/'work.sqlite')
    restored.authorize(space['space_id'], space['token'])
    with pytest.raises(LookupError):
        restored.authorize(space['space_id'], 'wrong')
    assert restored.claim(now=100)['id'] == identifier
    assert restored.claim(now=101) is None
    # Restart after a lost worker recovers its lease.
    assert restored.claim(now=281)['id'] == identifier
    restored.pause(space['space_id'], identifier)
    restored.finish(identifier, 'observing', {'risk':'no alert'}, now=282)
    assert restored.claim(now=1000) is None
    assert restored.list(space['space_id'])[0]['active'] == 0
    other = restored.add(space['space_id'], 'lp', {'position_id':1}, now=100)
    assert restored.claim(now=100+86401) is None
    assert next(r for r in restored.list(space['space_id']) if r['id']==other)['state']=='expired'


def test_health_recovery_alert_and_source_failure(tmp_path, monkeypatch):
    journal = Journal(tmp_path/'work.sqlite')
    space = journal.create_space()
    identifier = journal.add(space['space_id'], 'health', {'account':'0x'+'11'*20,'threshold':1.25,'target':1.5})
    async def low(_):
        return {'health_factor':'1.1','debt_usd':'100','weighted_collateral_usd':'110'}
    monkeypatch.setattr(worker, 'observe_health', low)
    row=journal.claim()
    asyncio.run(worker.process(journal, ROOT, row))
    record = journal.list(space['space_id'])[0]
    assert record['state']=='alert'
    assert record['latest']['external_notification_sent'] is False
    assert record['events'][0]['kind']=='alert'
    assert record['events'][0]['read_at'] is None
    async def broken(_):
        raise ValueError('source unavailable')
    monkeypatch.setattr(worker, 'observe_health', broken)
    asyncio.run(worker.process(journal, ROOT, row))
    assert journal.list(space['space_id'])[0]['latest']['risk_state']=='unknown'
    journal.acknowledge(space['space_id'],identifier)
    assert all(e['read_at'] for e in journal.list(space['space_id'])[0]['events'])


def test_delivery_worker_does_not_notify_or_pay_submitted_job(tmp_path, monkeypatch):
    journal=Journal(tmp_path/'work.sqlite');space=journal.create_space()
    journal.add(space['space_id'],'order',{'job_id':56741,'notify_provider':True})
    async def status(**_):
        return {'status':'SUBMITTED', 'job_id':56741}
    async def delivery(**_):
        return {'acceptance': {'passed':False,'failures':['wrong price']}}
    async def forbidden(*_, **__):
        pytest.fail('Submitted jobs must not request another delivery')
    monkeypatch.setattr(worker, 'live_job_status', status)
    monkeypatch.setattr(worker, 'live_delivery', delivery)
    monkeypatch.setattr(worker, 'notify_live_agent', forbidden)
    asyncio.run(worker.process(journal,ROOT,journal.claim()))
    record=journal.list(space['space_id'])[0]
    assert record['state']=='acceptance_failed'
    assert record['latest']['transaction_sent'] is False


def test_private_api_consent_isolation_and_export(tmp_path):
    async def scenario():
        app=FastAPI();journal=Journal(tmp_path/'work.sqlite');app.include_router(make_router(ROOT,journal,enabled=True))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            one=(await client.post('/api/workspace/spaces')).json()
            two=(await client.post('/api/workspace/spaces')).json()
            path='/api/workspace/spaces/'+one['space_id']
            headers={'Authorization':'Bearer '+one['token']}
            assert (await client.get(path)).status_code==401
            assert (await client.get(path,headers={'Authorization':'Bearer '+two['token']})).status_code==404
            assert (await client.post(path+'/watches',headers=headers,json={'kind':'order','job_id':56741,'consent':False})).status_code==422
            assert (await client.post(path+'/watches',headers=headers,json={'kind':'order','job_id':56741,'consent':True})).status_code==200
            result=await client.get(path,headers=headers)
            assert one['token'] not in result.text
            assert len(result.json()['watches'])==1
    asyncio.run(scenario())


def test_chainhelix_followup_exact_budget_and_wrong_budget_rejection(monkeypatch):
    value={'client':'0x'+'11'*20, 'status':'OPEN', 'budget_raw':'0',
           'description':{'price':str(reviewed_grid.PRICE)}, 'task_spec':{}, 'description_verification':{},
           'open_progress':{'registered_policy':live_erc8183.POLICY,'allowance_raw':'0'}}
    async def status(**_): return copy.deepcopy(value)
    monkeypatch.setattr(live_erc8183, 'live_job_status', status)
    plan=asyncio.run(live_erc8183.live_followup_plan(buyer=value['client'],job_id=56741))
    assert plan['price_raw']==str(reviewed_grid.PRICE)
    assert [t['step'] for t in plan['transactions']]==['set_budget','approve_u','fund_job']
    from eth_abi import decode
    approval=plan['transactions'][1]
    assert decode(['address','uint256'],bytes.fromhex(approval['data'][10:]))[1]==reviewed_grid.PRICE
    value['budget_raw']=str(reviewed_grid.PRICE+1)
    with pytest.raises(ValueError):
        asyncio.run(live_erc8183.live_followup_plan(buyer=value['client'],job_id=56741))


def test_notification_budget_is_global_and_survives_restart(tmp_path):
    journal=Journal(tmp_path/'work.sqlite')
    assert journal.reserve_notification(56741,now=100)
    assert not journal.reserve_notification(56741,now=101)
    second=Journal(tmp_path/'work.sqlite')
    assert second.reserve_notification(56741,now=400)
    assert second.reserve_notification(56741,now=700)
    assert not second.reserve_notification(56741,now=1000)


def test_yield_costs_can_make_hold_better():
    from proofops.workspace.market import yield_comparison
    observation={'markets':[{'venue_id':'venus-core-usdt','projected_supply_apy_pct':'3'},
                            {'venue_id':'venus-core-usdc','projected_supply_apy_pct':'4'}]}
    spec={'capital':1000,'days':30,'cost':10,'minimum_gain':1,'current_venue':'venus-core-usdt'}
    result=yield_comparison(observation,spec)
    assert result['best_under_assumptions']=='venus-core-usdt'
    assert not result['triggered'] and not result['migration_ready']
    assert result['capacity'] is None
    result=yield_comparison(observation,spec|{'cost':0,'minimum_gain':0})
    assert result['best_under_assumptions']=='venus-core-usdc' and result['triggered']


def test_registry_gate_rejects_wrong_token_or_wallet():
    from proofops.services.submission import _registry_observation_valid
    catalog=json.loads((ROOT/'evidence/marketplace/live-agent-catalog.json').read_text())
    item=next(a for a in catalog['agents'] if a['token_id']==269224)
    assert _registry_observation_valid(item)
    assert not _registry_observation_valid(item|{'token_id':269225})
    assert not _registry_observation_valid(item|{'provider_address':'0x'+'11'*20})
    changed=copy.deepcopy(item)
    changed['registration_observation']['return_data']='0x'+'00'*32
    assert not _registry_observation_valid(changed)
