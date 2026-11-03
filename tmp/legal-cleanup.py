import pathlib,importlib.util,subprocess,json
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,urllib.request,asyncio
token=sys.stdin.readline().strip()
def call(path,method='GET'):
 request=urllib.request.Request('http://localhost:8075/api/v1'+path,method=method,headers={'Authorization':'Bearer '+token})
 with urllib.request.urlopen(request,timeout=20) as response:return json.load(response)
title='Conferência técnica fictícia: CPC, art. 12; data de referência: 2020-01-01. Não há processo ou pessoa real neste teste.'[:80]
rows=[c for c in call('/chats') if c['title']==title and c['created_at'].startswith('2026-10-30T14:07:')]
from moara.gateway.database import Database
from moara.gateway.settings import Settings
async def clean_sessions():
 db=Database(Settings.load());revoked=0
 for c in rows:
  sessions=await db.execute("""SELECT s.id FROM moara.sessions s JOIN moara.chats c ON c.account_id=s.account_id
    WHERE c.id=CAST(:chat AS uuid) AND s.created_at BETWEEN c.created_at-interval '20 seconds' AND c.created_at
    AND s.revoked_at IS NULL""",{'chat':c['id']})
  if len(sessions)==1:
   await db.execute('UPDATE moara.sessions SET revoked_at=now() WHERE id=CAST(:id AS uuid)',{'id':str(sessions[0]['id'])});revoked+=1
 await db.dispose();return revoked
revoked=asyncio.run(clean_sessions())
for c in rows:assert call('/chats/'+c['id'],'DELETE')['deleted']
print(json.dumps({'obsolete_synthetic_chats_removed':len(rows),'identified_obsolete_test_sessions_revoked':revoked,'unrelated_chats_untouched':True}))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session()+'\n',capture_output=True,text=True,timeout=50)
print(r.stdout,flush=True)
if r.returncode:print(r.stderr[-1200:]);raise SystemExit(r.returncode)
