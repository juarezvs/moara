"""Real SDK acceptance test. Credentials only arrive on stdin and never enter report."""
import sys,json,time,hashlib,ssl,io,zipfile,re
from pathlib import Path
import httpx,yaml
from openai import OpenAI,AuthenticationError,PermissionDeniedError
fixture=json.loads(sys.stdin.readline());base=fixture['base'];checks={};keys=[];session_hash=None
report=Path('/artifacts/ide-sdk.json');http=httpx.Client(timeout=180,trust_env=False,verify=ssl.create_default_context(cafile='/ca.crt'))
def save():report.write_text(json.dumps({'checks':checks,'test_key_ids':keys,'test_session_sha256':session_hash},indent=2))
def api(path,method='GET',**kwargs):return http.request(method,base+'/api/v1'+path,**kwargs)
headers={}
try:
 r=api('/auth/session','POST',headers={'Authorization':'Bearer '+fixture['token']});assert r.status_code==200
 cookie=r.cookies.get('__Secure-moara_session');session_hash=hashlib.sha256(cookie.encode()).hexdigest();save()
 headers={'Cookie':'__Secure-moara_session='+cookie,'x-moara-csrf':r.json()['csrf_token']}
 r=api('/developer/keys','POST',headers=headers,json={'name':'IDE acceptance synthetic','rpm':60,'validity_days':1});assert r.status_code==201,(r.status_code,r.text[:200])
 value=r.json();keys.append(value['id']);key=value['token'];save()
 checks['personal_key_created']=key.startswith('moara_')
 listing=api('/developer/keys',headers=headers);assert key not in listing.text and 'token_hash' not in listing.text;checks['secret_not_retrievable']=True
 bundle=api('/developer/continue.zip',headers=headers);assert bundle.status_code==200
 with zipfile.ZipFile(io.BytesIO(bundle.content)) as z:
  conf=yaml.safe_load(z.read('config.yaml'));model=conf['models'][0]
  assert model['apiBase'].endswith('/moara/v1') and model['model']=='moara-code' and model['useResponsesApi'] is False
  assert model['requestOptions']['verifySsl'] is True and 'tool_use' in model['capabilities']
  assert all(key.encode() not in z.read(n) for n in z.namelist())
 checks['continue_bundle_valid_no_secret']=True
 sdk=OpenAI(api_key=key,base_url=base+'/v1',http_client=http,max_retries=0)
 assert 'moara-code' in [x.id for x in sdk.models.list()];assert sdk.models.retrieve('moara-code').id=='moara-code';checks['sdk_models']=True
 prompt='Software fixture: return only Python code, without markdown or explanation. Implement normalize_name(value: str) -> str to strip leading/trailing whitespace, collapse runs of whitespace to one space and lowercase. Do not add test code.'
 start=time.monotonic();result=sdk.chat.completions.create(model='moara-code',messages=[{'role':'user','content':prompt}],max_tokens=256,temperature=0)
 assert result.model=='moara-code';code=result.choices[0].message.content or '';code=re.sub(r'^```(?:python)?\s*|\s*```$','',code.strip())
 assert 'def normalize_name' in code;Path('/artifacts/ide-generated.py').write_text(code)
 checks['sdk_code_generation']=True;checks['gpu_execution']=result.model_extra.get('moara',{}).get('execution_backend')=='gpu';checks['response_seconds']=round(time.monotonic()-start,2)
 chunks=list(sdk.chat.completions.create(model='moara-code',messages=[{'role':'user','content':'Reply with exactly: MOARA_OK'}],stream=True,max_tokens=32,temperature=0))
 nonempty=[c for c in chunks if c.choices];assert nonempty and len({c.id for c in nonempty})==1 and all(c.created and c.model=='moara-code' for c in nonempty)
 assert ''.join(c.choices[0].delta.content or '' for c in nonempty);checks['sdk_streaming_stable_envelope']=True
 tools=[{'type':'function','function':{'name':'read_project_file','description':'Read a synthetic software source file.','parameters':{'type':'object','properties':{'path':{'type':'string','enum':['example.py']}},'required':['path'],'additionalProperties':False}}}]
 messages=[{'role':'user','content':'Inspect example.py using read_project_file. Do not invent its contents.'}]
 result=sdk.chat.completions.create(model='moara-code',messages=messages,tools=tools,tool_choice={'type':'function','function':{'name':'read_project_file'}},max_tokens=128,temperature=0)
 call=result.choices[0].message.tool_calls[0];assert json.loads(call.function.arguments)=={'path':'example.py'};checks['sdk_tool_call']=True
 messages += [result.choices[0].message.model_dump(exclude_none=True),{'role':'tool','tool_call_id':call.id,'content':'def add(a, b):\n    return a - b\n'}]
 result=sdk.chat.completions.create(model='moara-code',messages=messages,tools=tools,tool_choice='none',max_tokens=256,temperature=0)
 assert result.choices[0].message.content;checks['sdk_tool_roundtrip']=True
 chunks=list(sdk.chat.completions.create(model='moara-code',messages=messages[:1],tools=tools,tool_choice={'type':'function','function':{'name':'read_project_file'}},stream=True,max_tokens=128,temperature=0))
 args=''.join(t.function.arguments or '' for c in chunks for choice in c.choices for t in choice.delta.tool_calls or [] if t.function)
 assert json.loads(args)=={'path':'example.py'};checks['sdk_stream_tool_arguments']=True
 limited={'Authorization':'Bearer '+key}
 for path in ['/developer/keys','/accounts','/data-sources']:
  r=api(path,headers=limited);assert r.status_code in (403,404),(path,r.status_code)
 checks['key_cannot_admin_or_issue_keys']=True
 try:sdk.chat.completions.create(model='juridical',messages=[{'role':'user','content':'test'}],max_tokens=8)
 except (PermissionDeniedError,Exception) as exc:assert getattr(exc,'status_code',None) in (403,404)
 else:raise AssertionError('unapproved profile allowed')
 checks['profile_allowlist_enforced']=True
 r=api('/developer/keys/'+keys[0]+'/revoke','POST',headers=headers);assert r.status_code==200
 try:sdk.models.list()
 except AuthenticationError:checks['revocation_blocks_sdk']=True
 else:raise AssertionError('revoked key accepted')
finally:
 for identifier in keys:
  try:api('/developer/keys/'+identifier+'/revoke','POST',headers=headers)
  except Exception:pass
 save()
print(json.dumps({'checks':checks,'passed':True}))
