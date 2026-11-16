"""Real ASGI adapter with explicitly substituted registry HTTP transport."""
import asyncio
import json
from unittest.mock import Mock
import httpx
import pytest
from controlplane_identity import nightly
from controlplane_identity.nightly_http import Authority,RunMiddleware
from test_nightly import BINDING,CLAIMS,SUB,TENANT

SCOPE=BINDING['scope']|dict(organization='',realm='controlplane',issuer='https://auth.test.hyperme.sh/realms/controlplane',clients=['controlplane-frontend'],origins=['https://portal.test.hyperme.sh'],identities={'sea':[]})
CONFIG=dict(version=1,owner='acl',origin='https://api.test.hyperme.sh',authOrigin='https://api.test.hyperme.sh',ownerKey='a'*64,controllerKey='b'*64,scopes={SCOPE['suite']:SCOPE})
PATH='/api/v1/acl/sociacl/device-transfer/current'


def setup(native):
    calls=[];active=[True]
    def registry(request):
        value=json.loads(request.content);calls.append(value)
        base=BINDING|{'owner':'acl','scope':SCOPE}
        if value['action']=='admit':return httpx.Response(200,json=base) if active[0] else httpx.Response(409,json={})
        if value['action']=='complete':return httpx.Response(200,json={k:base[k] for k in ('version','owner','run','generation','operation')}|{'completed':True})
        raise AssertionError('unexpected command')
    authority=Authority(CONFIG,'acl',httpx.MockTransport(registry))
    return RunMiddleware(native,authority,{('POST',PATH)},'/api/v1/acl/internal/nightly-run'),calls,active


@pytest.mark.asyncio
async def test_native_work_finishes_before_completion_and_closed_grant_never_dispatches(monkeypatch):
    monkeypatch.setattr(nightly,'_subjects',frozenset())
    entered=asyncio.Event();finish=asyncio.Event()
    async def native(scope,receive,send):
        nightly.require_original_run(CLAIMS);entered.set();await finish.wait()
        await send(dict(type='http.response.start',status=200,headers=[]));await send(dict(type='http.response.body',body=b'{}'))
    app,calls,active=setup(native)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://api.test.hyperme.sh') as client:
        request=asyncio.create_task(client.post(PATH,headers={'X-Nightly-Run-Grant':'d'*64}))
        await entered.wait();assert [v['action'] for v in calls]==['admit']
        active[0]=False;finish.set();assert (await request).status_code==200
        assert [v['action'] for v in calls]==['admit','complete']
        assert (await client.post(PATH,headers={'X-Nightly-Run-Grant':'d'*64})).status_code==409


@pytest.mark.asyncio
async def test_unknown_effect_or_foreign_route_never_completes(monkeypatch):
    monkeypatch.setattr(nightly,'_subjects',frozenset())
    async def native(scope,receive,send):raise RuntimeError('unknown native completion')
    app,calls,_=setup(native)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='https://api.test.hyperme.sh') as client:
        assert (await client.post(PATH,headers={'X-Nightly-Run-Grant':'d'*64})).status_code==409
        assert (await client.post('/foreign',headers={'X-Nightly-Run-Grant':'d'*64})).status_code==409
    assert [v['action'] for v in calls]==['admit']
