import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from eth_abi.abi import decode, encode
from eth_utils.crypto import keccak
from fastapi import FastAPI

from proofops.arena.financial_sources import COMPTROLLER, MARKETS, UNDERLYINGS
from proofops.workspace import actions, supply
from proofops.workspace.routes import ActionRequest, make_router
from proofops.workspace.store import Journal

ROOT = Path(__file__).resolve().parents[1]
HASH = '0x'+'ab'*32
OWNER = '0x'+'11'*20
OPTIONS = ActionRequest(consent=True).model_dump(exclude={'consent'})


def observation(name):
    result = json.loads((ROOT/f'evidence/marketplace/service-followup-2026-09-08/{name}-source.json').read_text())
    result.update(block_timestamp=int(datetime.now(UTC).timestamp()),block_hash=HASH)
    return result


class Reader:
    def __init__(self, *, cap=0, allowance=0, return_code=0, paused=False, reorganized=False):
        self.cap,self.allowance,self.return_code,self.paused,self.reorganized=cap,allowance,return_code,paused,reorganized
        self.calls=[]

    async def canonical_block_hash(self, number):
        return '0x'+'cd'*32 if self.reorganized else HASH

    async def rpc(self, method, params):
        assert method=='eth_call', 'Preparation may never broadcast'
        tx, ref=params
        assert ref=={'blockHash':HASH,'requireCanonical':True}
        self.calls.append(tx)
        selector=tx['data'][:10]
        def matches(signature):return selector=='0x'+keccak(text=signature)[:4].hex()
        values={'protocolPaused()':(['bool'],[False]),'getCash()':(['uint256'],[50*10**18]),
                'totalBorrows()':(['uint256'],[100*10**18]),'totalReserves()':(['uint256'],[10*10**18]),
                'supplyCaps(address)':(['uint256'],[self.cap]),'actionPaused(address,uint8)':(['bool'],[self.paused]),
                'comptroller()':(['address'],[COMPTROLLER]),'underlying()':(['address'],[UNDERLYINGS['venus-core-usdt']]),
                'decimals()':(['uint8'],[18]),'borrowBalanceCurrent(address)':(['uint256'],[10*10**18]),
                'balanceOf(address)':(['uint256'],[20*10**18]),'allowance(address,address)':(['uint256'],[self.allowance]),
                'repayBorrow(uint256)':(['uint256'],[self.return_code]),
                'decreaseLiquidity((uint256,uint128,uint256,uint256,uint256))':(['uint256','uint256'],[10**18,2*10**18])}
        for signature,(types,args) in values.items():
            if matches(signature):return '0x'+encode(types,args).hex()
        if matches('multicall(bytes[])'):
            return '0x'+encode(['bytes[]'],[[encode(['uint256','uint256'],[10**18,2*10**18]),encode(['uint256','uint256'],[10**18+100,2*10**18+100])]]).hex()
        raise AssertionError('Unexpected selector '+selector)


@pytest.mark.parametrize('bad',['0','-1','NaN','Infinity','1000001','0.0000000000000000001'])
def test_token_amount_bounds(bad):
    with pytest.raises(ValueError):actions.token_amount(bad)


def test_token_amount_does_not_round_small_units():
    assert actions.token_amount('0.000000000000000001')==1
    assert actions.token_amount('999999.123456789123456789')==999999123456789123456789


def test_capacity_zero_cap_is_not_unlimited_and_same_block():
    obs=observation('yield');reader=Reader(cap=0)
    result=asyncio.run(actions.venus_capacity(obs,reader=reader))
    assert all(r['supply_room_token_units']=='0' for r in result['markets'])
    assert all(r['cash_token_units']=='50' for r in result['markets'])
    result=asyncio.run(actions.venus_capacity(obs,reader=Reader(cap=150*10**18,paused=True)))
    assert all(r['supply_room_token_units']=='10' and r['mint_paused'] for r in result['markets'])
    with pytest.raises(ValueError,match='reorganized'):
        asyncio.run(actions.venus_capacity(obs,reader=Reader(reorganized=True)))


def test_health_stress_and_zero_debt_are_not_false_protection():
    obs={'debt_usd':'100','weighted_collateral_usd':'150','health_factor':'1.5'}
    result=actions.health_scenarios(obs,1.5,20,10)
    assert result['stressed_health_factor'].startswith('1.0909')
    assert result['required_external_repay_usd']=='30.00'
    result=actions.health_scenarios(obs|{'debt_usd':'0','health_factor':None},1.5,20,10)
    assert result['stressed_health_factor'] is None
    assert result['required_external_repay_usd']=='0.00'


def test_repayment_nonzero_error_is_failure_not_success(monkeypatch):
    async def health(_):return observation('health')
    monkeypatch.setattr(actions,'observe_health',health)
    reader=Reader(allowance=2*10**18,return_code=7)
    monkeypatch.setattr(actions,'BscReader',lambda:reader)
    result=asyncio.run(actions.prepare_action({'kind':'health','spec':{'account':OWNER,'target':1.5}},OPTIONS|{'amount':'2'}))
    assert result['simulation']['passed'] is False
    assert result['blockers']
    assert result['drafts'][0]['from']==OWNER and not result['drafts'][0]['ready_to_send']
    assert all(tx['to']==MARKETS['venus-core-usdt'] for tx in result['drafts'])


def test_repayment_requires_exact_allowance_and_never_simulates_unapproved(monkeypatch):
    async def health(_):return observation('health')
    monkeypatch.setattr(actions,'observe_health',health)
    reader=Reader(allowance=10**18)
    monkeypatch.setattr(actions,'BscReader',lambda:reader)
    result=asyncio.run(actions.prepare_action({'kind':'health','spec':{'account':OWNER,'target':1.5}},OPTIONS|{'amount':'2'}))
    assert len(result['drafts'])==3
    assert 'simulation' not in result
    first,second,_=result['drafts']
    assert decode(['address','uint256'],bytes.fromhex(first['data'][10:]))[1]==0
    assert decode(['address','uint256'],bytes.fromhex(second['data'][10:]))[1]==2*10**18
    assert result['ready_to_send'] is False


def test_lp_exit_draft_preserves_owner_and_minimums(monkeypatch):
    async def lp(_):return observation('lp')
    monkeypatch.setattr(actions,'observe_lp',lp)
    reader=Reader();monkeypatch.setattr(actions,'BscReader',lambda:reader)
    result=asyncio.run(actions.prepare_action({'kind':'lp','spec':{'position_id':7319347}},OPTIONS|{'simulate_lp_exit':True}))
    tx=result['drafts'][0]
    batch=decode(['bytes[]'],bytes.fromhex(tx['data'][10:]))[0]
    exit_args=decode(['(uint256,uint128,uint256,uint256,uint256)'],batch[0][4:])[0]
    collect_args=decode(['(uint256,address,uint128,uint128)'],batch[1][4:])[0]
    assert exit_args[0]==7319347
    assert exit_args[2:4]==(995000000000000000,1990000000000000000)
    assert collect_args[1].lower()==result['observation']['owner'].lower()==tx['from'].lower()
    assert result['simulation']['passed'] and not result['trade_executed']
    assert result['blockers'], 'Withdrawal is not complete rebalancing'


def test_grid_high_costs_reject_positive_profit_claim(monkeypatch):
    async def grid():return observation('grid')
    monkeypatch.setattr(actions,'observe_grid_market',grid)
    result=asyncio.run(actions.prepare_action({'kind':'grid','spec':{'lower':700,'upper':800}},OPTIONS|{'gas_per_order':100}))
    assert result['metrics']['net_adjacent_cycle_usd']<0
    assert all(r['state']=='unsubmitted_plan' for r in result['plan_levels'])
    assert not result['trade_executed'] and result['drafts']==[]


def test_probe_projection_expires_and_does_not_promote_failure():
    assert not supply.status(None)['can_request_quote']
    value={'state':'quote_verified','checked_at':100,'expires_at':1000}
    assert supply.status(value,now=101)['can_request_quote']
    assert not supply.status(value,now=461)['can_request_quote']
    assert not supply.status(value|{'expires_at':100},now=101)['can_request_quote']
    assert not supply.status(value|{'state':'unavailable'},now=101)['can_request_quote']


def test_private_action_endpoint_isolation_consent_and_resume(tmp_path,monkeypatch):
    async def fake(row,options):return {'kind':row['kind'],'ready_to_send':False,'trade_executed':False,'plan_hash':'test-only'}
    monkeypatch.setattr(actions,'prepare_action',fake)
    async def scenario():
        journal=Journal(tmp_path/'work.sqlite');app=FastAPI();app.include_router(make_router(ROOT,journal,enabled=True))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            cred=(await c.post('/api/workspace/spaces')).json();other=(await c.post('/api/workspace/spaces')).json()
            headers={'Authorization':'Bearer '+cred['token']};base='/api/workspace/spaces/'+cred['space_id']
            watch=(await c.post(base+'/watches',headers=headers,json={'kind':'grid','consent':True})).json()['watch_id']
            path=base+'/watches/'+watch
            assert (await c.post(path+'/action-plan',headers={'Authorization':'Bearer '+other['token']},json={'consent':True})).status_code==404
            assert (await c.post(path+'/action-plan',headers=headers,json={'consent':False})).status_code==422
            assert (await c.post(path+'/action-plan',headers=headers,json={'consent':True,'amount':'1e18'})).status_code==422
            assert (await c.post(path+'/action-plan',headers=headers,json={'consent':True})).status_code==200
            assert journal.watch(cred['space_id'],watch)['events'][0]['kind']=='action_plan'
            await c.post(path+'/pause',headers=headers,json={})
            assert journal.watch(cred['space_id'],watch)['active']==0
            assert (await c.post(path+'/resume',headers=headers,json={})).status_code==200
            assert journal.watch(cred['space_id'],watch)['active']==1
    asyncio.run(scenario())


def test_log_source_failover_and_fail_closed(monkeypatch):
    async def run():
        import httpx
    
        from proofops.services import live_erc8183
        seen=[]
        fail_all=False
        class Client:
            def __init__(self,**kwargs):pass
            async def __aenter__(self):return self
            async def __aexit__(self,*args):pass
            async def post(self,url,json):
                seen.append((url,json['method']))
                request=httpx.Request('POST',url)
                if 'publicnode' in url or fail_all:
                    return httpx.Response(403,request=request)
                return httpx.Response(200,json={'result':[]},request=request)
        monkeypatch.delenv('SAFEHIRE_BSC_LOG_RPC',raising=False)
        monkeypatch.setattr(live_erc8183.httpx,'AsyncClient',Client)
        assert await live_erc8183._rpc('eth_getLogs',[{}])==[]
        assert seen==[('https://bsc-rpc.publicnode.com','eth_getLogs'),('https://bsc.drpc.org','eth_getLogs')]
        fail_all=True
        with pytest.raises(ValueError,match='current state unverified'):
            await live_erc8183._rpc('eth_getLogs',[{}])
    asyncio.run(run())


def test_receipt_hint_requires_canonical_exact_job(monkeypatch):
    async def run():
        from proofops.services import live_erc8183 as m
        tx='0x'+'a'*64
        receipt={'status':'0x1','transactionHash':tx,'blockNumber':'0x10','blockHash':HASH}
        log={'address':m.POLICY,'topics':[m.JOB_INITIALISED_TOPIC,m._topic_uint(56741)],'transactionHash':tx,'blockNumber':'0x10','blockHash':HASH}
        receipt['logs']=[log]
        async def rpc(method,params):
            return receipt if method=='eth_getTransactionReceipt' else {'hash':HASH}
        monkeypatch.setattr(m,'_rpc',rpc)
        assert await m._receipt_delivery_log(56741,tx)==log
        with pytest.raises(ValueError,match='exact job'):
            await m._receipt_delivery_log(56742,tx)
        receipt['blockHash']='0x'+'b'*64
        with pytest.raises(ValueError,match='canonical'):
            await m._receipt_delivery_log(56741,tx)
    asyncio.run(run())
