import pathlib,subprocess,json,importlib.util
root=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
code=r'''
import sys,json,httpx
from moara.gateway.settings import Settings,secret
from moara.legal_mcp.contracts import today
token=sys.stdin.read().strip();question='crie uma peti\u00e7\u00e3o para aposentadoria de um pescador, segurado especial, com fundamenta\u00e7\u00e3o jur\u00eddica robusta.\nMODO DE TRABALHO: prepare um RASCUNHO para revis\u00e3o humana. Preserve campos pendentes e diferencie fatos informados de hip\u00f3teses. N\u00e3o pratique atos oficiais.'
with httpx.Client(trust_env=False,timeout=240) as c:
 r=c.post('http://localhost:8075/api/v1/chat/completions',headers={'Authorization':'Bearer '+token},json={'model':'auto','messages':[{'role':'user','content':question}],'max_tokens':2200});r.raise_for_status()
 baseline=r.json()
 r=c.post(Settings.load().legal_mcp_url,headers={'Authorization':'Bearer '+secret('moara_legal_key'),'MCP-Protocol-Version':'2025-11-25'},json={'jsonrpc':'2.0','id':1,'method':'tools/call','params':{'name':'recover_legal_sources','arguments':{'reference_date':str(today()),'query':'aposentadoria pescador segurado especial','subject_query':'aposentadoria pescador segurado especial'}}});r.raise_for_status()
 print(json.dumps({'baseline':baseline,'research':r.json()},ensure_ascii=True))
'''
r=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-c',code],input=m.admin_session(),capture_output=True,text=True,timeout=450)
if r.returncode:raise RuntimeError(r.stderr[-1200:])
data=json.loads(r.stdout);(root/'tmp/legal-draft-probe.json').write_text(json.dumps(data))
p=data.get('research',{}).get('result',{}).get('structuredContent',{})
print(json.dumps({'baseline_answer':data['baseline']['choices'][0]['message']['content'],'research_status':p.get('status'),'norms':[{'norm':n.get('norm'),'source':n.get('source'),'devices':[e.get('device') for e in n.get('excerpts',[])]} for n in p.get('norms',[])]},ensure_ascii=True))
