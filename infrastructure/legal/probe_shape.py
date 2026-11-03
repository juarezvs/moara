import subprocess
code=r'''
import asyncio,json,traceback
import httpx
from moara.legal_mcp.sources import OfficialSources,sequence,validated_identity,extract
from moara.legal_mcp.contracts import Norm,today
async def main():
 async with httpx.AsyncClient(trust_env=False) as c:
  adapter=OfficialSources(c);s=Norm(kind='LEI',number=8112,year=1990)
  d,_=await adapter.fetch('https://legis.senado.leg.br/dadosabertos/legislacao/LEI/8112/1990.json')
  ident=sequence(d['DetalheDocumento']['documentos']['documento'])[0]['identificacao'];urn=validated_identity(ident,s)
  d,_=await adapter.fetch('https://normas.leg.br/api/public/normas?urn='+urn+'&&tipo_documento=maior-detalhe')
  print(json.dumps({'urn':urn,'keys':list(d),'hasPart_type':type(d.get('hasPart')).__name__,'sample':str(d.get('hasPart'))[:1800]},ensure_ascii=True))
  try:ex,gaps=extract(d,[],str(today()));print(json.dumps({'excerpts':len(ex),'gaps':gaps}))
  except Exception:traceback.print_exc()
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-legal-mcp-1','python','-'],input=code,text=True,capture_output=True,timeout=75)
print(r.stdout);print(r.stderr[-2200:])
