import subprocess
code=r'''
import asyncio,re,json
import httpx
from moara.legal_mcp.sources import clean
async def main():
 urls=['https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num=1157','https://scon.stj.jus.br/repetitivos/temas_repetitivos/pesquisa.jsp?novaConsulta=true&tipo_pesquisa=T&cod_tema_inicial=1157&cod_tema_final=1157']
 async with httpx.AsyncClient(trust_env=False,timeout=20) as c:
  for url in urls:
   r=await c.get(url);html=r.text
   print(json.dumps({'url':url,'snippets':[clean(html[max(0,m.start()-180):m.end()+300]) for m in list(re.finditer(r'Tese|Descri.{0,10}o:|Quest.o submetida|situa.{0,8}o do tema|1157',html,re.I))[:18]],'scripts':re.findall(r'<script[^>]+src=["\x27]([^"\x27]+)',html)[-12:]},ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-legal-mcp-1','python','-'],input=code,text=True,capture_output=True,timeout=70)
print(r.stdout);print(r.stderr[-500:])
