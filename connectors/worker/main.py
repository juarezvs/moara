import asyncio
import base64
import hashlib
import hmac
import json
import multiprocessing
import os
import time
import uuid
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from common.contracts import WorkerCall, METHODS
from common.policy import Rejected
from common.policy import validate_ip

KIND=os.environ['CONNECTOR_KIND']
KEY=Path('/run/secrets/connector_key').read_text().strip()
FORBIDDEN=json.loads(os.environ.get('FORBIDDEN_NETWORKS','[]'))
SLOTS=asyncio.Semaphore(2)
app=FastAPI(title='Curumim Connector '+KIND,version='1.0.0',docs_url=None,redoc_url=None)

def capabilities():
    unavailable={'list_schemas'} if KIND in {'mongodb','rest'} else set()
    if KIND!='postgres':unavailable.add('authorize_secp')
    return {'type':KIND,'version':'1.0.0','readonly':True,'methods':{name:name not in unavailable for name in METHODS},
        'query_language':'bounded_select' if KIND in {'postgres','mysql','mssql','oracle','sqlite'} else 'bounded_find' if KIND=='mongodb' else 'get_head',
        'schema_sampling':KIND in {'mongodb','rest'},'max_concurrency':2}

async def auth(request:Request):
    header=request.headers.get('authorization','')
    if not hmac.compare_digest(header,'Bearer '+KEY):raise HTTPException(401,'Serviço não autenticado')

@app.exception_handler(RequestValidationError)
async def invalid(request,exc):return JSONResponse({'detail':'Parâmetros inválidos'},422)

@app.get('/health')
async def health():return {'ok':True,'type':KIND}

@app.get('/v1/capabilities',dependencies=[Depends(auth)])
async def get_capabilities():return capabilities()

@app.post('/v1/resolve',dependencies=[Depends(auth)])
async def resolve(request:Request):
    import socket
    body=await request.json();host=body.get('host','');port=body.get('port',0)
    if not isinstance(host,str) or len(host)>253 or any(c in host for c in '/@;\\\r\n') or not isinstance(port,int) or not 1<=port<=65535:
        raise HTTPException(422,'Host ou porta inválidos')
    try:
        addresses=await asyncio.to_thread(socket.getaddrinfo,host,port,0,socket.SOCK_STREAM)
        result=sorted({validate_ip(r[4][0],FORBIDDEN) for r in addresses})
        return {'addresses':result}
    except Exception:raise HTTPException(422,'Endereço não permitido ou não resolvido') from None

def child(send,body):
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU,(body['connection']['timeout']+2,body['connection']['timeout']+3))
        resource.setrlimit(resource.RLIMIT_FSIZE,(16*1024**2,16*1024**2))
        if KIND in {'mongodb','rest'}:
            from document_driver import mongo,rest
            result=(mongo if KIND=='mongodb' else rest)(body,FORBIDDEN)
        else:
            from sql_driver import run
            result=run(KIND,body,FORBIDDEN)
        send.send({'ok':True,'result':result})
    except Rejected as exc:send.send({'ok':False,'error':str(exc),'type':'policy'})
    except Exception as exc:send.send({'ok':False,'error':'Falha na conexão ou consulta. Verifique TLS, privilégio de leitura e disponibilidade.','type':type(exc).__name__})
    finally:send.close()

@app.post('/v1/call',dependencies=[Depends(auth)])
async def call(body:WorkerCall):
    if not capabilities()['methods'].get(body.method):raise HTTPException(422,'Capacidade indisponível neste conector')
    if SLOTS.locked():raise HTTPException(429,'Conector ocupado; tente novamente')
    async with SLOTS:
        receive,send=multiprocessing.get_context('spawn').Pipe(duplex=False)
        process=multiprocessing.get_context('spawn').Process(target=child,args=(send,body.model_dump()))
        start=time.monotonic();process.start();send.close()
        try:
            deadline=start+min(body.connection.timeout,body.policy.timeout)+5
            while not receive.poll():
                if not process.is_alive():raise HTTPException(502,'Driver encerrou a consulta')
                if time.monotonic()>deadline:raise HTTPException(504,'Tempo limite do conector excedido')
                await asyncio.sleep(.05)
            result=receive.recv()
            print(json.dumps({'event':'connector_call','type':KIND,'method':body.method,'ok':result['ok'],
                'duration_ms':round((time.monotonic()-start)*1000),'error_type':result.get('type')}),flush=True)
            if not result['ok']:raise HTTPException(422 if result['type']=='policy' else 502,result['error'])
            return result['result']
        finally:
            if process.is_alive():process.terminate()
            await asyncio.to_thread(process.join,2)
            if process.is_alive():process.kill();await asyncio.to_thread(process.join,1)
            receive.close()

@app.post('/v1/import-sqlite',dependencies=[Depends(auth)])
async def import_sqlite(request:Request):
    if KIND!='sqlite':raise HTTPException(404)
    raw=await request.body()
    if len(raw)>8*1024**2 or not raw.startswith(b'SQLite format 3\x00'):raise HTTPException(422,'Envie SQLite de até 8 MB')
    folder=Path('/data/sqlite');folder.mkdir(exist_ok=True,parents=True)
    identifier=str(uuid.uuid4());path=folder/(identifier+'.db');path.write_bytes(raw);path.chmod(0o440)
    if SLOTS.locked():path.unlink(missing_ok=True);raise HTTPException(429,'Conector ocupado; tente novamente')
    async with SLOTS:
        receive,send=multiprocessing.get_context('spawn').Pipe(duplex=False)
        process=multiprocessing.get_context('spawn').Process(target=validate_snapshot,args=(send,str(path)))
        process.start();send.close();deadline=time.monotonic()+5
        try:
            while not receive.poll():
                if time.monotonic()>deadline or not process.is_alive():raise ValueError()
                await asyncio.sleep(.05)
            if receive.recv() is not True:raise ValueError()
        except asyncio.CancelledError:
            path.unlink(missing_ok=True);raise
        except Exception:
            path.unlink(missing_ok=True)
            raise HTTPException(422,'SQLite inválido ou verificação excedeu o limite') from None
        finally:
            if process.is_alive():process.terminate()
            await asyncio.to_thread(process.join,1)
            if process.is_alive():process.kill();await asyncio.to_thread(process.join,1)
            receive.close()
    return {'sqlite_id':identifier,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def validate_snapshot(send,path):
    """Parse untrusted database files in a disposable, CPU/memory bounded child."""
    try:
        import resource,sqlite3
        resource.setrlimit(resource.RLIMIT_CPU,(3,4));resource.setrlimit(resource.RLIMIT_AS,(512*1024**2,512*1024**2))
        db=sqlite3.connect('file:'+path+'?mode=ro&immutable=1',uri=True)
        db.setlimit(sqlite3.SQLITE_LIMIT_LENGTH,1024**2);db.setlimit(sqlite3.SQLITE_LIMIT_COLUMN,256)
        deadline=time.monotonic()+3;db.set_progress_handler(lambda:int(time.monotonic()>deadline),1000)
        db.execute('PRAGMA trusted_schema=OFF');valid=db.execute('PRAGMA quick_check').fetchone()[0]=='ok';db.close();send.send(valid)
    except Exception:send.send(False)
    finally:send.close()
