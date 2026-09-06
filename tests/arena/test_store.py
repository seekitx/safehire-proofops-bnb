from __future__ import annotations
import copy,json,sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from proofops.arena.examples import examples
from proofops.arena.models import TaskSpec,canonical
from proofops.arena.planners import reference_proposal
from proofops.arena.store import TaskStore,Conflict,MissingTask,CapacityError,parse_proposal,verify_bundle


def sample(tmp_path,**kwargs):
    store=TaskStore(tmp_path/'tasks.sqlite3',**kwargs)
    task=TaskSpec.model_validate(examples()['tasks']['rebalancing'])
    created=store.create(task)
    raw=canonical(reference_proposal(task).model_dump())
    return store,task,created,raw


def test_persistence_roundtrip_bytes_and_offline_verification(tmp_path):
    s,t,c,raw=sample(tmp_path)
    result=s.submit(c['task_id'],c['task_token'],raw,request_key='request-1',expected_version=1)
    s=TaskStore(tmp_path/'tasks.sqlite3')
    bundle=s.bundle(c['task_id'],c['task_token'])
    assert bundle['proposals'][0]['raw_text']==raw
    assert bundle['integrity']['valid'] and verify_bundle(bundle)['valid']
    assert verify_bundle(bundle,trusted_head=bundle['integrity']['head'])['valid']
    assert not verify_bundle(bundle,trusted_head='f'*64)['valid']
    assert 'task_token' not in json.dumps(bundle) and 'token_hash' not in json.dumps(bundle)
    assert not bundle['paid_delivery_verified']


def test_exact_idempotent_retry_and_byte_conflict(tmp_path):
    s,t,c,raw=sample(tmp_path)
    kw=dict(request_key='request-1',expected_version=1)
    a=s.submit(c['task_id'],c['task_token'],raw,**kw)
    b=s.submit(c['task_id'],c['task_token'],raw,**kw)
    assert b['replayed'] and a['proposal_id']==b['proposal_id']
    with pytest.raises(Conflict):s.submit(c['task_id'],c['task_token'],raw+' ',**kw)
    with pytest.raises(Conflict):s.submit(c['task_id'],c['task_token'],raw,request_key='request-2',expected_version=1)


@pytest.mark.parametrize('operation',['read','write'])
def test_other_task_capability_cannot_access(tmp_path,operation):
    s,t,c,raw=sample(tmp_path);other=s.create(t)
    with pytest.raises(MissingTask):
        if operation=='read':s.bundle(c['task_id'],other['task_token'])
        else:s.submit(c['task_id'],other['task_token'],raw,request_key='request-1',expected_version=1)


def test_atomic_concurrency_one_writer_one_conflict(tmp_path):
    s,t,c,raw=sample(tmp_path)
    def submit(n):
        try:return s.submit(c['task_id'],c['task_token'],raw,request_key=f'request-{n}',expected_version=1)
        except Conflict:return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(submit,[1,2]))
    assert sum(r=='conflict' for r in results)==1
    assert s.bundle(c['task_id'],c['task_token'])['integrity']['valid']


def test_quotas_do_not_partially_write(tmp_path):
    s,t,c,raw=sample(tmp_path,max_tasks=1,max_proposals=1)
    with pytest.raises(CapacityError):s.create(t)
    s.submit(c['task_id'],c['task_token'],raw,request_key='request-1',expected_version=1)
    with pytest.raises(CapacityError):s.submit(c['task_id'],c['task_token'],raw,request_key='request-2',expected_version=2)
    assert s.bundle(c['task_id'],c['task_token'])['version']==2


@pytest.mark.parametrize('target',['raw','event','report','task','tail'])
def test_tampering_detected(tmp_path,target):
    s,t,c,raw=sample(tmp_path)
    s.submit(c['task_id'],c['task_token'],raw,request_key='request-1',expected_version=1)
    b=s.bundle(c['task_id'],c['task_token']);b.pop('bundle_sha256')
    if target=='raw':b['proposals'][0]['raw_text']+=' '
    elif target=='event':b['events'][0]['event_json']='{}'
    elif target=='report':b['proposals'][0]['report_json']='{"policy_accepted":false}'
    elif target=='task':b['task']['limits']['max_cost_usd']=999
    else:b['events'].pop()
    assert not verify_bundle(b)['valid']


def test_expired_task_cannot_be_created_but_stale_output_is_recorded_as_blocked(tmp_path):
    s,t,c,raw=sample(tmp_path)
    future=t.snapshot.observed_at+timedelta(seconds=3600)
    with pytest.raises(ValueError):s.create(t,now=future)
    r=s.submit(c['task_id'],c['task_token'],raw,request_key='request-1',expected_version=1,now=future)
    assert not r['report']['policy_accepted']


@pytest.mark.parametrize('text',['{"a":1,"a":2}','[]','{}','null','x'*24001])
def test_malformed_and_duplicate_json_rejected(text):
    with pytest.raises(ValueError):parse_proposal(text)
