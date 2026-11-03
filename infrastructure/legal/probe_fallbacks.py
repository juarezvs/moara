import subprocess
code=r'''
import asyncio,json
import httpx
from moara.legal_mcp.sources import OfficialSources,clean
async def main():
 urls=['https://www.planalto.gov.br/ccivil_03/leis/l8112cons.htm','https://www.planalto.gov.br/ccivil_03/leis/l8112compilado.htm','https://www2.camara.leg.br/legin/fed/lei/1990/lei-8112-11-dezembro-1990-322161-normaatualizada-pl.html','https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=1157','https://scon.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?novaConsulta=true&tipo_pesquisa=T&cod_tema_inicial=1157&cod_tema_final=1157']
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=12) as c:
  for url in urls:
   try:
    r=await c.get(url);print(json.dumps({'url':url,'status':r.status_code,'bytes':len(r.content),'sample':clean(r.text)[-200:]},ensure_ascii=True),flush=True)
   except Exception as e:print(json.dumps({'url':url,'error':type(e).__name__}),flush=True)
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-legal-mcp-1','python','-'],input=code,text=True,capture_output=True,timeout=100)
print(r.stdout);print(r.stderr[-500:])
