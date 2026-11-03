import importlib.util,json,ssl,urllib.request,subprocess
from pathlib import Path
ROOT=Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
token=m.admin_session();ctx=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/moara-domain-root-ca.crt'))
def call(path,method=None):
 req=urllib.request.Request('https://moara.am.trf1.gov.br'+path,headers={'Authorization':'Bearer '+token},method=method)
 with urllib.request.urlopen(req,context=ctx,timeout=40) as response:return json.load(response)
try:
 listing=call('/api/v1/chats/?page=1')
 if isinstance(listing,dict):listing=listing.get('items',listing.get('data',[]))
 matches=[]
 for row in listing[:5]:
  if not 1793113612<=row.get('created_at',0)<=1793113625:continue
  d=call('/api/v1/chats/'+row['id']);messages=list(d.get('chat',{}).get('history',{}).get('messages',{}).values())
  users=[x for x in messages if x.get('role')=='user']
  if len(users)==1 and users[0].get('content')=='Quem é você?' and not users[0].get('files'):matches.append(row['id'])
 assert len(matches)<=1,'ambiguous cleanup'
 for identifier in matches:call('/api/v1/chats/'+identifier,'DELETE')
 print(json.dumps({'final_synthetic_chat_removed':len(matches)}))
 cfg=call('/api/v1/retrieval/embedding')
 assert cfg['RAG_EMBEDDING_BATCH_SIZE']==16 and cfg['RAG_EMBEDDING_CONCURRENT_REQUESTS']==1
 r=json.loads((ROOT/'docs/runtime/embedding-upload-validation-20261027.json').read_text())
 samples=r['progress_samples'];values=[x['percent'] for x in samples if x.get('percent') is not None]
 assert values==sorted(values) and values[-1]==100
 assert r['passed'] and r['synthetic_file_removed'] and r['retrieved_chunks']>0
 summary={k:r[k] for k in ['bytes','processing_status','elapsed_seconds','retrieved_chunks','passed','synthetic_file_removed','webui_embedding_statuses_during_validation']}
 summary.update(percent_monotonic=True,total_chunks=samples[-1]['total_chunks'],waiting_observed=any(x['stage']=='waiting' for x in samples),batch_size=cfg['RAG_EMBEDDING_BATCH_SIZE'])
 before=json.loads((ROOT/'docs/runtime/chat-feedback-20261027/containers-before.json').read_text())
 after={x['Names']:x['ID'] for x in [json.loads(line) for line in subprocess.check_output(['docker','ps','--format','{{json .}}'],text=True).splitlines()]}
 assert all(after.get(k)==v for k,v in before.items() if k!='ai-server-webui-1')
 summary['other_containers_unchanged']=True
 summary['webui_health']=subprocess.check_output(['docker','inspect','-f','{{.State.Health.Status}}','ai-server-webui-1'],text=True).strip()
 assert summary['webui_health']=='healthy'
 print(json.dumps(summary))
finally:call('/api/v1/auths/signout','POST')
