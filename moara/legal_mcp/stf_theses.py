"""Fresh public STF thesis text, tied to the independently checked theme identity."""
import asyncio,base64,gzip,hashlib,re
from datetime import datetime,timezone
import httpx
from .stf_catalog import ENDPOINT,PORTAL,ROBOT,AGENT,decode_bank
from .catalog import tracked
from .contracts import today
from moara.research_browser.policy import RobotsRules

async def bank(adapter):
 result={'items':[],'snapshots':[],'source_checks':[],'gaps':[]}
 async def download(method,url,data=None):
  attempt={'source':'STF thesis catalogue','url':url,'method':method,'form':data,'attempted_at':datetime.now(timezone.utc).isoformat()};result['source_checks'].append(attempt)
  try:
   async with adapter.slots:
    async with adapter.client.stream(method,url,data=data,headers={'User-Agent':AGENT,'Cache-Control':'no-cache'},follow_redirects=False,timeout=20) as response:
     response.raise_for_status();raw=bytearray()
     async for part in response.aiter_bytes():
      raw.extend(part)
      if len(raw)>(65536 if url==ROBOT else 8*1024**2):raise ValueError('stf_theses_response_too_large')
     raw=bytes(raw);sha=hashlib.sha256(raw).hexdigest()
     snapshot={'url':url,'method':method,'form':data,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':sha,'bytes':len(raw),'content_type':response.headers.get('content-type'),'snapshot_gzip_base64':base64.b64encode(gzip.compress(raw,mtime=0)).decode(),'role':'provider_access_policy_not_legal_evidence' if url==ROBOT else 'fresh_official_published_theses'}
     result['snapshots'].append(snapshot);attempt.update(status='retrieved',sha256=sha);return raw
  except (httpx.HTTPError,ValueError) as error:
   attempt.update(status='unavailable',failure=type(error).__name__)
   if isinstance(error,httpx.HTTPStatusError):attempt['http_status']=error.response.status_code
   raise
 try:
  policy=await download('GET',ROBOT)
  if not RobotsRules(policy.decode('utf8')).can_fetch(AGENT,ENDPOINT):raise ValueError('stf_theses_access_disallowed')
  result['items']=decode_bank(await download('POST',ENDPOINT,{'tipo':'com'}),'com')
 except (httpx.HTTPError,ValueError,KeyError,TypeError):result['gaps'].append('Não foi possível conferir o texto divulgado no banco oficial de teses nesta consulta. O acervo local não substituiu essa conferência.')
 return result

async def attach(adapter,record):
 meta=record.get('official_theme')
 if not meta:return
 # One download per research adapter, shared by concurrent theme checks. Never
 # cached across questions or substituted by the older local discovery corpus.
 if not hasattr(adapter,'_fresh_theses_task'):adapter._fresh_theses_task=asyncio.create_task(bank(adapter))
 result=await asyncio.shield(adapter._fresh_theses_task)
 record['snapshots'].extend(result['snapshots']);record['source_checks'].extend(result['source_checks']);record['gaps'].extend(result['gaps'])
 found=[r for r in result['items'] if r['theme']==meta['number']]
 if len(found)!=1:return
 row=found[0]
 if row['leading_case']!=meta['leading_case']:
  record['gaps'].append('O processo do banco de teses diverge do cadastro do tema; o texto não foi utilizado.');return
 record['published_thesis']={'text':row['thesis_text'],'source':PORTAL,'retrieval_endpoint':ENDPOINT,'retrieved_at':result['snapshots'][-1]['retrieved_at'],'record_sha256':row['record_sha256'],'freshly_rechecked':True,'bank':'com','leading_case':row['leading_case'],'effective_application_confirmed':False}
 record['excerpts'].append({'device':'STF TEMA '+str(meta['number'])+' TESE DIVULGADA','text':row['thesis_text'],'source':PORTAL,'version_date':str(today()),'effective_date_confirmed':False,'freshly_rechecked':True})

def related(record):
 text=record.get('published_thesis',{}).get('text','');own=record.get('reference',{}).get('number')
 return list(dict.fromkeys(int(n.replace('.','')) for n in re.findall(r'\btema\s+(\d{1,3}(?:\.\d{3})+|\d{1,5})(?!\d)',text,re.I) if int(n.replace('.',''))!=own))[:3]
