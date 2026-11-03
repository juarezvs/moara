import pathlib,subprocess,json
root=pathlib.Path(__file__).resolve().parents[2]
code=r'''
import asyncio,json,gzip,base64,hashlib,httpx
from moara.legal_mcp.web_recovery import web_references
from moara.legal_mcp.contracts import Norm
async def main():
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as c:
  r=await web_references(c,'diálogo competitivo',[Norm(kind='LEI',number=14133,year=2021)])
  print(json.dumps({'provider':r.get('provider'),'status':r['status'],'accepted_leads':len(r['hints']),'normative_evidence':r['normative_evidence'],'snapshots_reproducible':bool(r.get('snapshots')) and all(hashlib.sha256(gzip.decompress(base64.b64decode(s['snapshot_gzip_base64']))).hexdigest()==s['sha256'] for s in r.get('snapshots',[]))}))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','ai-server-moara-legal-mcp-1','python','-c',code],capture_output=True,text=True,check=True)
report=json.loads(r.stdout);assert report['normative_evidence'] is False
(root/'docs/runtime/legal-recovery-web-provider.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
