"""Read only public official API contracts and sample norm identities."""
import json,pathlib,urllib.request,concurrent.futures
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/legal-api-diagnostic';folder.mkdir(exist_ok=True)
urls={
 'senado-openapi':'https://legis.senado.leg.br/dadosabertos/v3/api-docs',
 'camara-openapi':'https://dadosabertos.camara.leg.br/api/v2/api-docs',
 'lei14133':'https://legis.senado.leg.br/dadosabertos/legislacao/LEI/14133/2021.json',
 'lei9868':'https://legis.senado.leg.br/dadosabertos/legislacao/LEI/9868/1999.json',
}
def get(item):
 name,url=item
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'Accept':'application/json','User-Agent':'Moara-LegalVerification/2.0'}),timeout=35) as r:
   raw=r.read(12*1024*1024+1);assert len(raw)<=12*1024*1024
  data=json.loads(raw);(folder/(name+'.json')).write_bytes(raw)
  if name.endswith('openapi'):
   paths={k:{m:{'summary':v.get('summary'),'parameters':v.get('parameters')} for m,v in vals.items() if isinstance(v,dict)} for k,vals in data.get('paths',{}).items() if ('legislacao' in k or k in ['/proposicoes','/proposicoes/{id}','/proposicoes/{id}/tramitacoes','/proposicoes/{id}/relacionadas'])}
   return {'name':name,'paths':paths}
  doc=data['DetalheDocumento']['documentos']['documento'][0]
  return {'name':name,'identity':doc['identificacao'],'keys':list(doc)}
 except Exception as e:return {'name':name,'error':type(e).__name__}
for result in concurrent.futures.ThreadPoolExecutor(max_workers=2).map(get,urls.items()):print(json.dumps(result,ensure_ascii=True))
