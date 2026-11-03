import pathlib,json,urllib.request,concurrent.futures
root=pathlib.Path(__file__).resolve().parents[2];folder=root/'tmp/legal-api-diagnostic'
for name in ['lei14133','lei9868']:
 doc=json.loads((folder/(name+'.json')).read_bytes())['DetalheDocumento']['documentos']['documento'][0]
 print(json.dumps({'name':name,'keys':list(doc),'identity':doc['identificacao'],'other':{k:v for k,v in doc.items() if k not in ['vides','disps','publicacoes','identificacao']},'changes_count':len(doc.get('vides',{}).get('vide',[]))},ensure_ascii=True))
urls={
 '14133-structured':'https://normas.leg.br/api/public/normas?urn=urn:lex:br:federal:lei:2021-04-01;14133&&tipo_documento=maior-detalhe',
 '9868-structured':'https://normas.leg.br/api/public/normas?urn=urn:lex:br:federal:lei:1999-11-10;9868&&tipo_documento=maior-detalhe',
 'camara-pl1292':'https://dadosabertos.camara.leg.br/api/v2/proposicoes?siglaTipo=PL&numero=1292&ano=1995&itens=5',
 'senado-list':'https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?tipo=LEI&numero=14133&ano=2021',
 'camara-norm':'https://www2.camara.leg.br/legin/fed/lei/2021/lei-14133-1-abril-2021-791222-normaatualizada-pl.html',
 'planalto':'https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm',
}
def get(item):
 name,url=item
 try:
  with urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Moara-LegalVerification/2.0','Accept':'application/json,text/html'}),timeout=20) as r:
   raw=r.read(12*1024*1024+1);assert len(raw)<=12*1024*1024
  (folder/(name+'.txt')).write_bytes(raw)
  if name.endswith('structured'):
   data=json.loads(raw);return {'name':name,'keys':list(data),'urn':data.get('legislationIdentifier'),'bytes':len(raw),'parts':len(data.get('hasPart',[]))}
  if name in ['senado-list','camara-pl1292']:return {'name':name,'data':json.loads(raw)}
  return {'name':name,'bytes':len(raw),'start':raw[:160].decode(errors='replace')}
 except Exception as e:return {'name':name,'error':str(e)[:140]}
for result in concurrent.futures.ThreadPoolExecutor(max_workers=2).map(get,urls.items()):print(json.dumps(result,ensure_ascii=True))
