"""Loopback-only mTLS transport for fixed Ollama backends; no request logging."""
import asyncio,contextlib,json,os,ssl,time
from pathlib import Path

SLOTS=asyncio.Semaphore(32)
CACHE={}

async def close(writer):
    if writer:
        writer.close()
        with contextlib.suppress(Exception):await writer.wait_closed()

async def relay(reader,writer):
    while chunk:=await asyncio.wait_for(reader.read(65536),timeout=300):
        writer.write(chunk);await asyncio.wait_for(writer.drain(),timeout=30)

async def proxy(reader,writer,port):
    upstream=None
    try:
        async with SLOTS:
            other,upstream=await asyncio.wait_for(asyncio.open_connection('127.0.0.1',port),timeout=3)
            tasks=[asyncio.create_task(relay(reader,upstream)),asyncio.create_task(relay(other,writer))]
            try:
                await asyncio.wait(tasks,return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:task.cancel()
                await asyncio.gather(*tasks,return_exceptions=True)
    except (OSError,TimeoutError,ssl.SSLError):pass
    finally:
        await close(upstream);await close(writer)

async def hardware():
    if time.monotonic()-CACHE.get('time',0)<5:return CACHE['value']
    value={'sampled_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'available':False}
    try:
        proc=await asyncio.create_subprocess_exec('/usr/bin/nvidia-smi',
            '--query-gpu=name,memory.total,memory.used,memory.free,temperature.gpu,utilization.gpu',
            '--format=csv,noheader,nounits',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
        raw,_=await asyncio.wait_for(proc.communicate(),timeout=3)
        if proc.returncode==0:
            rows=[]
            for line in raw.decode().splitlines():
                name,total,used,free,temp,util=[part.strip() for part in line.split(',')]
                rows.append({'name':name,'memory_total_mib':int(total),'memory_used_mib':int(used),
                    'memory_free_mib':int(free),'temperature_c':int(temp),'utilization_percent':int(util)})
            value.update(available=True,gpus=rows)
    except (OSError,ValueError,TimeoutError):
        if 'proc' in locals() and proc.returncode is None:
            proc.kill();await proc.wait()
    CACHE.update(time=time.monotonic(),value=value);return value

async def metrics(reader,writer):
    try:
        header=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),timeout=5)
        first=header.split(b'\r\n',1)[0]
        status='200 OK' if first==b'GET /status HTTP/1.1' else '404 Not Found'
        body=json.dumps(await hardware() if status.startswith('200') else {'error':'not_found'}).encode()
        writer.write(('HTTP/1.1 '+status+'\r\nContent-Type: application/json\r\nCache-Control: no-store\r\nConnection: close\r\nContent-Length: '+str(len(body))+'\r\n\r\n').encode()+body)
        await writer.drain()
    except (OSError,TimeoutError,asyncio.IncompleteReadError,asyncio.LimitOverrunError):pass
    finally:await close(writer)

async def main():
    directory=Path(os.environ['CREDENTIALS_DIRECTORY'])
    ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.minimum_version=ssl.TLSVersion.TLSv1_2
    ctx.load_cert_chain(directory/'server.crt',directory/'server.key')
    ctx.load_verify_locations(cafile=str(directory/'ca.crt'));ctx.verify_mode=ssl.CERT_REQUIRED
    servers=[]
    for listen,target in [(11443,11434),(11444,11435)]:
        servers.append(await asyncio.start_server(lambda r,w,p=target:proxy(r,w,p),'127.0.0.1',listen,
            ssl=ctx,ssl_handshake_timeout=5,limit=65536,backlog=32))
    servers.append(await asyncio.start_server(metrics,'127.0.0.1',11445,ssl=ctx,ssl_handshake_timeout=5,limit=4096,backlog=16))
    print('MOARA_GPU_MTLS_READY',flush=True)
    await asyncio.gather(*(server.serve_forever() for server in servers))

if __name__=='__main__':asyncio.run(main())
