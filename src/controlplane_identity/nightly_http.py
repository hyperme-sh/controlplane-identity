"""Bounded owner transport and ASGI dispatch for the TEST run registry."""
import asyncio
import hashlib
import hmac
import json
import re
import httpx
from controlplane_identity.nightly import admitted_run, configure_subjects, require

HEX=re.compile('[a-f0-9]{64}')
OWNERS={'acl','edge','user'}


def fields(value,names):require(type(value) is dict and set(value)==set(names.split()))


def configuration(value,owner):
    fields(value,'version owner origin authOrigin ownerKey controllerKey scopes')
    require(type(value['version']) is int and value['version']==1 and value['owner']==owner and owner in OWNERS)
    require(value['origin']=='https://api.test.hyperme.sh' and value['authOrigin']=='https://api.test.hyperme.sh')
    require(all(isinstance(value[k],str) and HEX.fullmatch(value[k]) for k in ('ownerKey','controllerKey'))
    require(value['ownerKey']!=value['controllerKey'])
    require(type(value['scopes']) is dict and 0<len(value['scopes'])<=5)
    for suite,scope in value['scopes'].items():
        fields(scope,'suite subject tenant organization realm issuer clients origins identities')
        require(scope['suite']==suite and scope['realm']=='controlplane' and scope['issuer']=='https://auth.test.hyperme.sh/realms/controlplane')
        # admitted_run validates the original native subject and tenant too.
        require(type(scope['clients']) is list and type(scope['origins']) is list and type(scope['identities']) is dict)
    return json.loads(json.dumps(value))


class Authority:
    def __init__(self,value,owner,transport=None):
        self.config=configuration(value,owner);self.transport=transport

    async def command(self,action,**fields):
        c=self.config;value=dict(version=1,owner=c['owner'],action=action,**fields)
        raw=json.dumps(value,separators=(',',':')).encode();require(len(raw)<=16384)
        signature=hmac.new(bytes.fromhex(c['ownerKey']),raw,hashlib.sha256).hexdigest()
        async with asyncio.timeout(12),httpx.AsyncClient(transport=self.transport,trust_env=False,follow_redirects=False,timeout=10) as client:
            async with client.stream('POST',c['authOrigin']+'/auth/nightly-run/v1/command',content=raw,
                headers={'Content-Type':'application/json','X-Nightly-Owner-Signature':signature}) as response:
                require(response.status_code==200);body=bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk);require(len(body)<=16384)
        result=json.loads(body);require(type(result) is dict and result.get('version')==1 and result.get('owner')==c['owner'])
        require(isinstance(result.get('generation'),str) and HEX.fullmatch(result['generation']) and isinstance(result.get('run'),str))
        if 'run' in fields:require(result['run']==fields['run'] and result['generation']==fields['generation'])
        if action=='admit':
            require(set(result)=={'version','owner','run','generation','scope','operation'})
            require(result['scope']==c['scopes'].get(result['scope'].get('suite')))
            # Validate before entering native work; this temporary context cannot escape.
            with admitted_run(result):pass
        elif action=='complete':
            require(set(result)=={'version','owner','run','generation','operation','completed'} and result['completed'] is True and result['operation']==fields['operation'])
        else:
            require(set(result)=={'version','owner','run','generation','phase','terminal_verified'}
                and result['phase'] in ('active','sealed','terminal') and result['terminal_verified'] is (result['phase']=='terminal'))
        return result

    async def control(self,raw,signature):
        c=self.config;require(len(raw)<=16384 and isinstance(signature,str) and HEX.fullmatch(signature))
        require(hmac.compare_digest(signature,hmac.new(bytes.fromhex(c['controllerKey']),raw,hashlib.sha256).hexdigest()))
        value=json.loads(raw);action=value.get('action')
        require(action in ('register','status','seal','retire'))
        fields(value,'version owner action run generation fence'+(' grant scope' if action=='register' else ''))
        require(type(value['version']) is int and value['version']==1 and value['owner']==c['owner'] and type(value['fence']) is int and value['fence']>0)
        if action=='register':require(value['scope']==c['scopes'].get(value['scope'].get('suite')))
        return await self.command(action,**{k:v for k,v in value.items() if k not in ('version','owner','action')})


class RunMiddleware:
    """Install outside transaction middleware; only successful native return completes."""
    def __init__(self,app,authority,paths,control_path):
        self.app,self.authority,self.paths,self.control_path=app,authority,set(paths),control_path
        configure_subjects([s['subject'] for s in authority.config['scopes'].values()])

    async def __call__(self,scope,receive,send):
        if scope['type']!='http':return await self.app(scope,receive,send)
        headers=scope.get('headers',[]);grants=[v for k,v in headers if k.lower()==b'x-nightly-run-grant']
        if scope['path']!=self.control_path and not grants:return await self.app(scope,receive,send)
        async def reply(value,status):
            await send({'type':'http.response.start','status':status,'headers':[(b'content-type',b'application/json'),(b'cache-control',b'private, no-store')]})
            await send({'type':'http.response.body','body':json.dumps(value).encode()})
        try:
            if scope['path']==self.control_path:
                require(scope['method']=='POST');raw=bytearray()
                async with asyncio.timeout(12):
                    while True:
                        message=await receive();require(message['type']=='http.request')
                        raw.extend(message.get('body',b''));require(len(raw)<=16384)
                        if not message.get('more_body',False):break
                signatures=[v.decode('ascii') for k,v in headers if k.lower()==b'x-nightly-controller-signature']
                require(len(signatures)==1)
                result=await self.authority.control(bytes(raw),signatures[0]);return await reply(result,200)
            require(len(grants)==1 and (scope['method'],scope['path']) in self.paths)
            grant=grants[0].decode('ascii');require(HEX.fullmatch(grant))
            binding=await self.authority.command('admit',grant=grant)
            messages=[];size=0
            async def buffer(message):
                nonlocal size
                require(message['type'] in ('http.response.start','http.response.body'))
                size+=len(message.get('body',b''));require(size<=8*1024*1024)
                require(len(messages)<4096)
                messages.append(message)
            with admitted_run(binding):
                await self.app(scope,receive,buffer)
            starts=[m for m in messages if m['type']=='http.response.start']
            require(len(starts)==1 and 200<=starts[0]['status']<400 and messages[-1]['type']=='http.response.body' and not messages[-1].get('more_body',False))
            await self.authority.command('complete',run=binding['run'],generation=binding['generation'],operation=binding['operation'])
            for message in messages:await send(message)
        except Exception:await reply({'error':'nightly-run-refused'},409)
