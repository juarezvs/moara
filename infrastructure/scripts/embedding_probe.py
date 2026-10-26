import json,subprocess
code="""import asyncio,json
from moara.gateway.settings import Settings
import httpx
async def main():
 settings=Settings.load()
 async with httpx.AsyncClient(trust_env=False) as client:
  r=await client.post(settings.legacy_gateway+'/v1/embeddings',headers={'Authorization':'Bearer '+settings.llm_key},json={'model':'embedding','input':['Documento fictício: o prazo de teste é de cinco dias.']},timeout=120)
  print(json.dumps({'status':r.status_code,'dimensions':len(r.json().get('data',[{}])[0].get('embedding',[])) if r.status_code==200 else 0,'synthetic_only':True}))
asyncio.run(main())
"""
p=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-'],input=code,text=True,capture_output=True,timeout=150)
print(p.stdout);print(p.stderr[-2000:]);raise SystemExit(p.returncode)
