import subprocess,pathlib,json
ROOT=pathlib.Path('/home/nutec/ai-server');target=json.loads((ROOT/'tmp/legal-grounding-stage.json').read_text())['mcp']
code=r'''
import asyncio,json,traceback
import httpx
from moara.legal_mcp.sources import OfficialSources
from moara.legal_mcp.contracts import Norm,today
from moara.legal_mcp.texts import current_encoding
async def main():
 async with httpx.AsyncClient(trust_env=False) as c:
  a=OfficialSources(c);structured,_=await a.fetch('https://normas.leg.br/api/public/normas?urn=urn:lex:br:federal:lei:1990-12-11;8112&&tipo_documento=maior-detalhe')
  result={'snapshots':[],'source_checks':[],'gaps':[]}
  try:
   e=await current_encoding(a,structured,Norm(kind='LEI',number=8112,year=1990),today(),result)
   print(json.dumps({'count':len(e),'devices':[v['device'] for v in e[:25]],'sample':str(e)[:1200]},ensure_ascii=True))
  except Exception:traceback.print_exc()
  print(json.dumps({'checks':result['source_checks']},ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',target,'python','-'],input=code,text=True,capture_output=True,timeout=70)
print(r.stdout);print(r.stderr[-2000:])
