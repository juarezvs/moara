import pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
code=r'''
import asyncio,httpx,json,re
from html.parser import HTMLParser
class Scripts(HTMLParser):
 def __init__(self):super().__init__();self.scripts=[]
 def handle_starttag(self,tag,attrs):
  if tag=='script' and dict(attrs).get('src'):self.scripts.append(dict(attrs)['src'])
async def main():
 async with httpx.AsyncClient(trust_env=False,timeout=25) as c:
  for url in ['https://portal.stf.jus.br/robots.txt','https://portal.stf.jus.br/repercussaogeral/teses.asp']:
   try:
    r=await c.get(url);parser=Scripts();parser.feed(r.text)
    print(json.dumps({'url':url,'status':r.status_code,'type':r.headers.get('content-type'),'text':r.text[:15000] if 'robots' in url else '', 'scripts':parser.scripts,'inline':[s[:14000] for s in re.findall(r'<script[^>]*>(.*?)</script>',r.text,re.S) if any(t in s.lower() for t in ['ajax','teses','pagin','listar'])]},ensure_ascii=True))
   except Exception as e:print(json.dumps({'url':url,'error':type(e).__name__}))
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','ai-server-moara-legal-mcp-1','python','-c',code],capture_output=True,text=True,timeout=80);print(r.stdout)
if r.returncode:print(r.stderr[-800:])
