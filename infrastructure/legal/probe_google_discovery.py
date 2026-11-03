import pathlib,json,subprocess,sys
root=pathlib.Path(__file__).resolve().parents[2];public='--public' in sys.argv
stage=json.loads((root/'tmp/google-discovery-stage.json').read_text());mcp='ai-server-moara-legal-mcp-1' if public else stage['mcp']
code=r'''
import asyncio,json,uuid,httpx
from pathlib import Path
from moara.legal_mcp.contracts import today
async def main():
 token=Path('/run/secrets/moara_legal_key').read_text().strip();headers={'Authorization':'Bearer '+token,'MCP-Protocol-Version':'2025-11-25'}
 async with httpx.AsyncClient(trust_env=False,timeout=55) as c:
  denied=await c.post('http://localhost:8076/mcp',json={'jsonrpc':'2.0','id':1,'method':'tools/list'})
  listed=await c.post('http://localhost:8076/mcp',headers=headers,json={'jsonrpc':'2.0','id':1,'method':'tools/list'});listed.raise_for_status()
  r=await c.post('http://localhost:8076/mcp',headers=headers,json={'jsonrpc':'2.0','id':2,'method':'tools/call','params':{'name':'discover_google_references','arguments':{'reference_date':str(today()),'subject_query':'hiv militar stf'}}});r.raise_for_status();value=r.json()['result']['structuredContent']
  browser_key=Path('/run/secrets/moara_google_browser_key').read_text().strip()
  b=await c.post('http://moara-google-browser:8077/references',json={'topic':'hiv militar'})
  invalid=await c.post('http://moara-google-browser:8077/references',headers={'Authorization':'Bearer '+browser_key},json={'topic':'hiv militar','url':'http://localhost/'})
  result={'checks':{'mcp_authentication_enforced':denied.status_code==401,'new_tool_exposed':any(t['name']=='discover_google_references' for t in listed.json()['result']['tools']),'browser_authentication_enforced':b.status_code==403,'arbitrary_navigation_rejected':invalid.status_code==422,'provider_outcome_explicit':value['status'] in {'search_leads_retrieved','provider_access_restricted','interactive_access_required','no_official_search_leads','search_unavailable','search_timeout'},'generated_text_never_evidence':value['normative_evidence'] is False and value['generated_answer_used'] is False,'no_legal_conclusion_from_search':not value.get('legal_conclusion_allowed',False)},'provider_result':value}
  print(json.dumps(result,ensure_ascii=True));assert all(result['checks'].values())
asyncio.run(main())
'''
r=subprocess.run(['docker','exec','-i',mcp,'python','-c',code],capture_output=True,text=True,timeout=100)
if r.returncode:raise RuntimeError('Provider validation failed: '+r.stderr[-1000:])
report=json.loads(r.stdout);report['tested_mcp_image']=subprocess.check_output(['docker','inspect',mcp,'--format','{{.Image}}'],text=True).strip()
(root/'docs/runtime'/('google-discovery-public.json' if public else 'google-discovery-stage.json')).write_text(json.dumps(report,indent=2,ensure_ascii=True));print(json.dumps({'checks':report['checks'],'provider_status':report['provider_result']['status'],'tested_mcp_image':report['tested_mcp_image']},ensure_ascii=True))
