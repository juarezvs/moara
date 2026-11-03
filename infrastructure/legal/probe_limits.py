import pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
code=r'''
import asyncio,json,re
import httpx
from moara.legal_mcp.sources import OfficialSources
async def main():
 urls=['https://www.gov.br/pncp/pt-br/pncp/legislacao/decretos','https://www.gov.br/compras/pt-br/acesso-a-informacao/comunicados/2025/no-47-25-decreto-altera-valores-da-lei-14-133-para-compras-publicas','https://www.in.gov.br/web/dou/-/decreto-n-12.807-de-29-de-dezembro-de-2025-678387990','https://www.planalto.gov.br/ccivil_03/_ato2023-2026/2025/decreto/d12807.htm']
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=20) as c:
  for url in urls:
   r=await c.get(url);text=r.text
   print(json.dumps({'url':url,'status':r.status_code,'bytes':len(r.content),'tables':len(re.findall('<table',text,re.I)),'has_annex':bool(re.search('130.984,20',text)),'content_type':r.headers.get('content-type')},ensure_ascii=True))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-legal-mcp-1','python','-'],input=code,text=True,capture_output=True,timeout=120)
print(r.stdout);print(r.stderr[-500:]);raise SystemExit(r.returncode)
