import subprocess,pathlib
code=r'''
import asyncio,json,time
import httpx
from moara.legal_mcp.sources import verify,OfficialSources
from moara.legal_mcp.contracts import Verification,Norm,today
async def main():
 async with httpx.AsyncClient(trust_env=False) as c:
  for articles in [[],['8','10','17']]:
   start=time.monotonic()
   try:
    value=await asyncio.wait_for(verify(c,Verification(reference_date=today(),norms=[Norm(kind='LEI',number=8112,year=1990,articles=articles)])),95)
    n=value.get('norms',[{}])[0];print(json.dumps({'articles':articles,'seconds':round(time.monotonic()-start,1),'status':n.get('status'),'excerpts':len(n.get('excerpts',[])),'snapshots':len(n.get('snapshots',[])),'bytes':len(json.dumps(value)),'sample':[{'device':e['device'],'text':e['text'][:400]} for e in n.get('excerpts',[]) if 'promo' in e['text'].lower()][:5]},ensure_ascii=True),flush=True)
   except Exception as e:print(json.dumps({'error':type(e).__name__,'detail':str(e)[:300],'seconds':round(time.monotonic()-start,1)}),flush=True)
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-legal-mcp-1','python','-'],input=code,text=True,capture_output=True,timeout=220)
print(r.stdout);print(r.stderr[-900:]);raise SystemExit(r.returncode)
