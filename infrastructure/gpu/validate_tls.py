"""Real transport tests: reject unauthenticated/wrong-CA/wrong-host connections."""
import pathlib,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
code=r'''
import asyncio,ssl,json,urllib.request
from pathlib import Path
from gpu_backend import GPUBackend
import os,httpx
async def main():
 result={};backend=GPUBackend.from_env(os.environ)
 async with httpx.AsyncClient(trust_env=False) as client:
  status=await backend.status(client)
  assert status['principal_resident'] and status['embeddings_resident'],status
  assert status['gpu']['available'],status
  result['status']=status
  for name,ca,certificate,hostname in [
    ('without_client_certificate',True,False,'moara-gpu-tunnel-tls'),
    ('untrusted_ca',False,True,'moara-gpu-tunnel-tls'),
    ('incorrect_server_identity',True,True,'127.0.0.1')]:
   context=ssl.create_default_context(cafile=os.environ['GPU_TLS_CA_FILE']) if ca else ssl.create_default_context()
   if certificate:context.load_cert_chain(os.environ['GPU_TLS_CERT_FILE'],os.environ['GPU_TLS_KEY_FILE'])
   try:
    reader,writer=await asyncio.wait_for(asyncio.open_connection('moara-gpu-tunnel-tls',11443,ssl=context,server_hostname=hostname),timeout=5)
    writer.write(b'GET /api/ps HTTP/1.1\r\nHost: moara-gpu-tunnel-tls\r\nConnection: close\r\n\r\n');await writer.drain()
    raw=await asyncio.wait_for(reader.read(1024),timeout=5);writer.close();await writer.wait_closed()
    assert not raw.startswith(b'HTTP/1.1 200'),name
   except (OSError,ssl.SSLError,TimeoutError):pass
   result[name]='rejected'
  response,where=await backend.chat(client,'moara-63af8a56-8192-12t','http://ollama:11434',
    {'messages':[{'role':'user','content':'Responda somente: transporte privado validado.'}],'max_tokens':32,'stream':True})
  assert where=='gpu' and response.status_code==200
  raw=await response.aread();await response.aclose();assert b'[DONE]' in raw
  result['streaming_gpu']='passed'
  embedding,where=await backend.embed(client,'http://ollama:11434','embeddinggemma:300m',['documento sintetico'],12)
  assert where=='gpu' and len(embedding.json()['embeddings'][0])==768
  result['embeddings_gpu']='passed'
 await backend.close();print(json.dumps(result))
asyncio.run(main())
'''
process=subprocess.run(['docker','exec','-i','moara-gateway-mtls-stage-20261030','python','-c',code],capture_output=True,text=True,timeout=120)
if process.returncode:raise RuntimeError(process.stderr[-2000:])
value=json.loads(process.stdout);(root/'docs/runtime/moara2-mtls-20261030.json').write_text(json.dumps(value,indent=2))
print(json.dumps(value))
