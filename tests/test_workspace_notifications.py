import asyncio
import json
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from proofops.workspace import notifications as m
from proofops.workspace.routes import make_router
from proofops.workspace.store import Journal


def test_encrypted_binding_verification_and_unsubscribe(tmp_path, monkeypatch):
    journal=Journal(tmp_path/'journal.db');space=journal.create_space()['space_id'];n=m.Notifications(journal)
    sent=[]
    async def send(key,title,body):sent.append((key,title,body));return True
    monkeypatch.setattr(m,'send_bark',send)
    secret='private-device-key-never-return'
    asyncio.run(n.bind(space,secret))
    assert not n.status(space)['enabled']
    assert secret.encode() not in journal.path.read_bytes()
    assert secret not in json.dumps(n.status(space))
    with journal.db() as db:row=dict(db.execute('SELECT * FROM push_channels').fetchone())
    assert n.unseal(space,row['secret'])==secret
    with pytest.raises(ValueError):n.unseal('different-space',row['secret'])
    code=sent[0][2].split('验证码：')[1][:6]
    n.verify(space,code)
    assert n.status(space)['verified'] and n.status(space)['enabled']
    n.unsubscribe(space)
    assert not n.status(space)['bound']
    with journal.db() as db:assert db.execute('SELECT secret FROM push_channels').fetchone()[0]==''


def test_wrong_codes_are_limited_and_persisted(tmp_path, monkeypatch):
    j=Journal(tmp_path/'journal.db');space=j.create_space()['space_id'];n=m.Notifications(j)
    async def send(*args):return True
    monkeypatch.setattr(m,'send_bark',send)
    monkeypatch.setattr(m.secrets,'randbelow',lambda n:123456)
    asyncio.run(n.bind(space,'a'*25))
    for _ in range(5):
        with pytest.raises(ValueError):n.verify(space,'000000')
    with pytest.raises(ValueError):n.verify(space,'123456')
    assert not n.status(space)['verified']
    with pytest.raises(ValueError):asyncio.run(n.bind(space,'b'*25))


def verified_channel(tmp_path,monkeypatch):
    j=Journal(tmp_path/'journal.db');space=j.create_space()['space_id'];n=m.Notifications(j)
    async def send(*args):return True
    monkeypatch.setattr(m,'send_bark',send);monkeypatch.setattr(m.secrets,'randbelow',lambda n:123456)
    asyncio.run(n.bind(space,'a'*25));n.verify(space,'123456')
    return j,space,n


def test_alert_queue_dedup_retry_and_restart(tmp_path,monkeypatch):
    j,space,n=verified_channel(tmp_path,monkeypatch)
    watch=j.add(space,'grid',{'lower':1,'upper':2})
    j.finish(watch,'alert',{'triggered':True});n.enqueue();n.enqueue()
    assert len(n.status(space)['deliveries'])==1
    sent=[]
    async def send(key,title,body):sent.append(body);return False
    monkeypatch.setattr(m,'send_bark',send)
    assert asyncio.run(n.deliver_one())
    assert n.status(space)['deliveries'][0]['state']=='pending'
    restarted=m.Notifications(Journal(j.path))
    for _ in range(2):
        with j.db() as db:db.execute('UPDATE push_outbox SET due=0')
        asyncio.run(restarted.deliver_one())
    record=n.status(space)['deliveries'][0]
    assert record['attempts']==3 and record['state']=='failed' and len(sent)==3
    assert not asyncio.run(n.deliver_one())
    assert watch not in sent[0] and '0x' not in sent[0]


def test_success_is_provider_acceptance_not_human_read(tmp_path,monkeypatch):
    j,space,n=verified_channel(tmp_path,monkeypatch)
    w=j.add(space,'health',{'account':'0x'+'1'*40});j.finish(w,'alert',{'triggered':True});n.enqueue()
    asyncio.run(n.deliver_one())
    assert n.status(space)['deliveries'][0]['state']=='accepted_by_provider'
    assert not asyncio.run(n.deliver_one())
    w2=j.add(space,'grid',{'lower':1,'upper':2});j.finish(w2,'alert',{});n.enqueue();n.unsubscribe(space)
    assert not asyncio.run(n.deliver_one())
    assert n.status(space)['deliveries'][0]['state']=='cancelled'


def test_no_opt_in_no_push_and_no_old_alerts(tmp_path,monkeypatch):
    j=Journal(tmp_path/'j.db');space=j.create_space()['space_id'];n=m.Notifications(j)
    w=j.add(space,'grid',{'lower':1,'upper':2});j.finish(w,'alert',{},now=1);n.enqueue()
    assert not n.status(space)['deliveries']


def test_notification_routes_require_own_token_and_consent(tmp_path,monkeypatch):
    j=Journal(tmp_path/'j.db');a=j.create_space();b=j.create_space();app=FastAPI();app.include_router(make_router(Path('.'),j,enabled=True))
    sent=[]
    async def send(*args):sent.append(args);return True
    monkeypatch.setattr(m,'send_bark',send)
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
            path='/api/workspace/spaces/'+a['space_id']+'/notifications'
            assert (await c.get(path)).status_code==401
            assert (await c.get(path,headers={'Authorization':'Bearer '+b['token']})).status_code==404
            h={'Authorization':'Bearer '+a['token']}
            assert (await c.post(path+'/bind',headers=h,json={'device_key':'a'*25,'consent':False})).status_code==422
            assert (await c.post(path+'/bind',headers=h,json={'device_key':'https://attacker.test/key','consent':True})).status_code==422
            assert not sent
            assert (await c.post(path+'/bind',headers=h,json={'device_key':'a'*25,'consent':True})).status_code==200
            assert 'a'*25 not in (await c.get(path,headers=h)).text
    asyncio.run(run())


def test_delivery_notice_once_and_crash_attempt_cap(tmp_path, monkeypatch):
    j,space,n=verified_channel(tmp_path,monkeypatch)
    watch=j.add(space,'order',{'job_id':123,'notify_provider':False})
    j.finish(watch,'submitted',{'delivery':{}})
    j.finish(watch,'submitted',{'delivery':{}})
    n.enqueue()
    assert len(n.status(space)['deliveries'])==1
    with j.db() as db: db.execute("UPDATE push_outbox SET state='sending',attempts=3,lease=0")
    assert not asyncio.run(n.deliver_one())
    assert n.status(space)['deliveries'][0]['state']=='failed'
