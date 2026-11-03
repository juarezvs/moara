import importlib.util,json,pathlib,subprocess,sys
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
container=sys.argv[1] if len(sys.argv)>1 else 'moara-legal-stage-http'
code=r'''
import sys,json,urllib.request,time,hashlib,base64,gzip
token=sys.stdin.readline().strip()
def call(path,body=None,accept='application/json',authenticate=True):
 headers={'Accept':accept}
 if authenticate:headers['Authorization']='Bearer '+token
 if body is not None:headers['Content-Type']='application/json'
 request=urllib.request.Request('http://localhost:8075'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
 with urllib.request.urlopen(request,timeout=120) as response:
  data=response.read()
  return json.loads(data) if accept=='application/json' else data.decode()
def chat(text,stream=False):
 start=time.monotonic()
 value=call('/api/v1/chat/completions',{'model':'auto','messages':[{'role':'user','content':text}],'max_tokens':64,'temperature':0,'stream':stream},'text/event-stream' if stream else 'application/json')
 return value,round(time.monotonic()-start,2)
report=[]
value,elapsed=chat('Analise juridicamente o art. 12 do CPC.')
assert value['moara']['legal_verification']['status']=='clarification_required'
report.append({'test':'clarification','passed':True,'seconds':elapsed})
for at,expected in [('2015-12-31',False),('2020-01-01',True)]:
 value,elapsed=chat('Confira o CPC, art. 12; data de referência: '+at)
 meta=value['moara']['legal_verification'];assert not meta['legal_conclusion_allowed']
 assert meta['status']=='verification_incomplete'
 evidence=call('/api/v1/legal/evidence/'+meta['evidence_id']+'?download=true')
 package=evidence['verification'];norm=package['norms'][0]
 assert norm['status']=='official_text_retrieved',norm['gaps']
 assert ('preferencialmente' in norm['excerpts'][0]['text'])==expected
 assert all(not excerpt['effective_date_confirmed'] for excerpt in norm['excerpts'])
 assert package['excerpt_selection']['status']=='selected',package['excerpt_selection']
 assert package['excerpt_selection']['execution_backend']=='gpu',package['excerpt_selection']
 for snapshot in norm['snapshots']:
  raw=gzip.decompress(base64.b64decode(snapshot['snapshot_gzip_base64']))
  assert hashlib.sha256(raw).hexdigest()==snapshot['sha256']
 canonical=json.dumps({'query':evidence['query'],'verification':package},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
 assert hashlib.sha256(canonical).hexdigest()==evidence['sha256']
 html=call('/api/v1/legal/evidence/'+meta['evidence_id'],accept='text/html')
 assert 'Vigência não confirmada' in html and '<main>' in html
 report.append({'test':'CPC_historical_'+at,'passed':True,'seconds':elapsed,'snapshots':len(norm['snapshots']),
                'excerpts':len(norm['excerpts']),'selection':package['excerpt_selection'],'source_checks':norm['source_checks'],'evidence_id':meta['evidence_id']})
value,elapsed=chat('CPC art. 12; data de referência: 2099-01-01',True)
assert 'legal_verification' in value and '2099-01-01' in value and '[DONE]' in value
report.append({'test':'SSE_future_date_guard','passed':True,'seconds':elapsed})
value,elapsed=chat('Quanto é 2 + 2? Responda somente o número.')
assert value['moara']['execution_backend']=='gpu',value['moara']
assert '4' in value['choices'][0]['message']['content']
report.append({'test':'normal_chat_GPU','passed':True,'seconds':elapsed})
print(json.dumps(report,ensure_ascii=True),flush=True)
'''
# Credentials travel only over SSH/docker stdin; never log them or put them in argv.
process=subprocess.run(['docker','exec','-i',container,'python','-c',code],input=m.admin_session()+'\n',text=True,capture_output=True,timeout=300)
print(process.stdout,flush=True)
if process.returncode:
    print(process.stderr[-2200:],flush=True);raise SystemExit(process.returncode)
