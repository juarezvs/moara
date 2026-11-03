"""Public metadata collector. Cataloguing is not confirmation of legal effectiveness.

Only the scheduled worker writes the catalogue. Chat reads an immutable version
and submits candidate identities to the existing mandatory official-text check.
"""
import argparse, asyncio, base64, gzip, hashlib, json, os, re, sqlite3
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import quote, urlencode, urlsplit
import httpx
from pydantic import BaseModel, ConfigDict, Field
from moara.research_browser.policy import RobotsRules
from .contracts import Norm, today
from .sources import clean, sequence, validated_identity

AGENT='Moara-MetadataCollector/1.0'
ROBOT='https://www.lexml.gov.br/robots.txt'
NOTICE='Catálogo referencial de cobertura federal parcial. Metadados, apelidos e links ajudam a localizar normas; não são o inteiro teor nem confirmam vigência, revogação, regras de transição ou efeitos judiciais. A resposta jurídica exige nova consulta ao texto oficial na data relevante.'
KINDS={'LEI':'lei','LCP':'lei.complementar','DEC':'decreto','DEL':'decreto.lei','EMC':'emenda.constitucional'}

class MetadataSearch(BaseModel):
 model_config=ConfigDict(extra='forbid')
 query:str=Field(default='',max_length=160)
 kind:str=Field(default='',pattern=r'^(LEI|LCP|DEC|DEL|EMC)?$')
 number:int|None=Field(default=None,ge=1,le=999999)
 year:int|None=Field(default=None,ge=1800,le=2100)
 page:int=Field(default=1,ge=1,le=10000)
 limit:int=Field(default=20,ge=1,le=50)

def stamp():return datetime.now(timezone.utc).isoformat()
def root_dir():return Path(os.getenv('MOARA_LEXML_CATALOG_DIR','/app/legal_catalog/lexml'))
def digest(raw):return hashlib.sha256(raw).hexdigest()
def norm_key(row):return (row['norm']['kind'],row['norm']['number'],row['norm']['year'])

def current(root=None):
 root=Path(root) if root else root_dir()
 try:
  version=(root/'CURRENT').read_text().strip()
  if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',version):return None
  folder=root/'versions'/version
  manifest=json.loads((folder/'manifest.json').read_text())
  if manifest.get('published') is not True or not (folder/'catalog.sqlite').is_file():return None
  return folder,manifest
 except (OSError,ValueError):return None

def search(spec,root=None):
 found=current(root)
 result={'available':bool(found),'items':[],'total':0,'page':spec.page,'limit':spec.limit,'notice':NOTICE,'legal_conclusion_allowed':False,'normative_text':False,'freshly_rechecked':False}
 if not found:return result
 folder,manifest=found;where=[];params=[];join=''
 for key,value in [('kind',spec.kind),('number',spec.number),('year',spec.year)]:
  if value:where.append('n.'+key+'=?');params.append(value)
 terms=re.findall(r'[^\W_]+',spec.query.casefold(),re.UNICODE)[:12]
 if terms:
  join=' JOIN norm_fts f ON f.rowid=n.id';where.append('norm_fts MATCH ?');params.append(' AND '.join('"'+t+'"' for t in terms))
 suffix=(' WHERE '+' AND '.join(where)) if where else ''
 with sqlite3.connect('file:'+quote(str(folder/'catalog.sqlite'))+'?mode=ro',uri=True) as db:
  result['total']=db.execute('SELECT count(*) FROM norms n'+join+suffix,params).fetchone()[0]
  order=' ORDER BY bm25(norm_fts),n.year DESC,n.number DESC' if terms else ' ORDER BY n.year DESC,n.number DESC'
  rows=db.execute('SELECT n.payload FROM norms n'+join+suffix+order+' LIMIT ? OFFSET ?',[*params,spec.limit,(spec.page-1)*spec.limit]).fetchall()
 result.update(items=[json.loads(r[0]) for r in rows],version=manifest['version'],collected_at=manifest['collected_at'],coverage=manifest['coverage'],counts=manifest['counts'])
 return result

def candidates(query,limit=5):
 # Local only. A query here can never become a URL or execute FTS syntax.
 found=search(MetadataSearch(query=query,limit=limit))
 return [{'norm':r['norm'],'name':r['name'],'summary':r['summary'],'aliases':r['aliases'],'source':r['catalogue_source'],'lexml_source':r['lexml_source'],'metadata_collected_at':r['metadata_collected_at'],'catalogue_version':found['version'],'discovery_only':True,'catalogue_rank':i+1,'lexml':r.get('lexml',{})} for i,r in enumerate(found['items'])]

def list_record(row,kind,source,collected_at):
 if str(row.get('tipo','')).split('-')[0]!=kind:raise ValueError('catalogue_kind_mismatch')
 number=int(str(row['numero']).replace('.',''));signed=datetime.strptime(row['dataassinatura'],'%d/%m/%Y').date()
 if str(row.get('anoassinatura',signed.year))!=str(signed.year):raise ValueError('catalogue_date_mismatch')
 norm=Norm(kind=kind,number=number,year=signed.year).model_dump()
 # A date is derived from official identification, never from a user's narrative.
 urn=f'urn:lex:br:federal:{KINDS[kind]}:{signed.isoformat()};{number}'
 return {'norm':norm,'urn':urn,'name':clean(row.get('normaNome'))[:500],'summary':clean(row.get('ementa'))[:6000],'aliases':clean(row.get('apelido'))[:2000],'signature_date':signed.isoformat(),'catalogue_source':source,'lexml_source':'https://www.lexml.gov.br/urn/'+urn,'metadata_collected_at':collected_at,'metadata_role':'discovery_only_not_normative_text'}

def evidence(rows,root=None):
 root=Path(root) if root else root_dir();found=current(root)
 if not found:return []
 wanted={norm_key(r) for r in rows};snapshots={}
 for row in json.loads((found[0]/'records.json').read_text()):
  if norm_key(row) not in wanted:continue
  for source in [row.get('catalogue_snapshot'),row.get('lexml',{}).get('snapshot')]:
   if not source:continue
   compressed=(root/'snapshots'/(source['sha256']+'.gz')).read_bytes()
   if digest(gzip.decompress(compressed))!=source['sha256']:raise ValueError('metadata_snapshot_corrupt')
   snapshots[source['sha256']]={**source,'snapshot_gzip_base64':base64.b64encode(compressed).decode()}
 return list(snapshots.values())

def jsonld_objects(value):
 if isinstance(value,list):
  for item in value:yield from jsonld_objects(item)
 elif isinstance(value,dict):
  yield value
  if '@graph' in value:yield from jsonld_objects(value['@graph'])

def parse_lexml(html,expected_urn):
 """Do not execute scripts, dereference JSON-LD contexts or follow listed links."""
 nodes=[]
 for raw in re.findall(r'<script\b[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',html,re.S|re.I):
  try:nodes.extend(jsonld_objects(json.loads(raw)))
  except ValueError:continue
 valid=[]
 for node in nodes:
  types=node.get('@type',[])
  if not isinstance(types,list):types=[types]
  if not any(str(t).rsplit('/',1)[-1]=='Legislation' for t in types):continue
  if node.get('legislationIdentifier')!=expected_urn:continue
  valid.append(node)
 if len(valid)>1:raise ValueError('ambiguous_jsonld_identity')
 # The current portal also publishes a labelled HTML record (no JSON-LD in
 # the production samples). Preserve this difference instead of inventing it.
 fields={}
 for label,value in re.findall(r'<strong>([^<]+)</strong>\s*</div>\s*<div\b[^>]*>(.*?)</div>',html,re.S|re.I):
  fields.setdefault(clean(label),[]).append(clean(value))
 html_ids=fields.get('Nome Uniforme',[])
 if html_ids and html_ids!=[expected_urn]:raise ValueError('lexml_html_identity_mismatch')
 if not valid and html_ids!=[expected_urn]:raise ValueError('lexml_identity_missing')
 node=valid[0] if valid else {}
 # Store known descriptive properties only. Original JSON/HTML is archived.
 props={key:node[key] for key in ('name','description','alternateName','legislationType','datePublished','legislationDate','legislationLegalForce','legislationChanges','legislationConsolidates','legislationAmends','legislationRepeals','isBasedOn','sameAs') if key in node}
 links=[]
 for raw in re.findall(r'<a\b[^>]*href=["\']([^"\']+)["\']',html,re.I):
  raw=unescape(raw);u=urlsplit(raw)
  if u.scheme not in ('http','https') or u.username or u.password or u.port not in (None,80,443):continue
  if u.hostname not in {'legis.senado.leg.br','normas.leg.br','www2.camara.gov.br','www2.camara.leg.br','legislacao.planalto.gov.br','www.planalto.gov.br','pesquisa.in.gov.br'}:continue
  if len(raw)<=2000 and raw not in links:links.append(raw)
 return {'format':'jsonld_legislation' if valid else 'labelled_html','identifier':expected_urn,'name':clean(node.get('name') or next(iter(fields.get('Título',[])),''))[:500],'aliases':fields.get('Apelido',[])[:10],'description':clean(node.get('description') or next(iter(fields.get('Ementa',[])),''))[:6000],'structured_properties':props,'provider_links':links[:30],'provider_links_checked':False,'normative_text':False,'legal_effectiveness_confirmed':False}

def archive(root,url,raw,content_type=''):
 sha=digest(raw);folder=root/'snapshots';folder.mkdir(exist_ok=True,parents=True);p=folder/(sha+'.gz')
 if not p.exists():p.write_bytes(gzip.compress(raw,mtime=0))
 return {'url':url,'retrieved_at':stamp(),'sha256':sha,'bytes':len(raw),'content_type':content_type,'role':'metadata_not_normative_text'}

async def harvest(root,plan,lexml_limit=30,transport=None,wait=asyncio.sleep):
 if plan.get('kinds'):
  plan={**plan,'feeds':[[kind,year] for year in (today().year,today().year-1) for kind in plan['kinds']]}
 root=Path(root);root.mkdir(parents=True,exist_ok=True)
 previous=current(root);old={}
 if previous:old={norm_key(r):r for r in json.loads((previous[0]/'records.json').read_text())}
 records=dict(old);snapshots=[];attempts=[];gaps=[]
 async with httpx.AsyncClient(transport=transport,trust_env=False,follow_redirects=False,timeout=25) as client:
  async def fetch(url):
   u=urlsplit(url)
   if u.scheme!='https' or u.hostname not in {'legis.senado.leg.br','www.lexml.gov.br'} or u.username or u.port not in (None,443):raise ValueError('collector_url_rejected')
   if u.hostname=='www.lexml.gov.br' and url!=ROBOT and not u.path.startswith('/urn/urn:lex:br:federal:'):raise ValueError('collector_path_rejected')
   attempt={'url':url,'attempted_at':stamp()};attempts.append(attempt)
   try:
    async with client.stream('GET',url,headers={'User-Agent':AGENT,'Accept':'application/json,text/html,text/plain','Cache-Control':'no-cache'}) as r:
     r.raise_for_status();raw=bytearray()
     async for part in r.aiter_bytes():
      raw.extend(part)
      if len(raw)>12*1024*1024:raise ValueError('collector_response_too_large')
     snap=archive(root,url,bytes(raw),r.headers.get('content-type',''));snapshots.append(snap);attempt.update(status='retrieved',sha256=snap['sha256']);return bytes(raw),snap
   except (httpx.HTTPError,ValueError) as e:
    attempt.update(status='unavailable',failure=type(e).__name__)
    if isinstance(e,httpx.HTTPStatusError):attempt['http_status']=e.response.status_code
    raise
  # A failed feed never replaces a previously complete catalogue.
  for kind,year in plan['feeds']:
   if kind not in KINDS or not 1800<=int(year)<=today().year:raise ValueError('invalid_feed')
   url='https://legis.senado.leg.br/dadosabertos/legislacao/lista.json?'+urlencode({'tipo':kind,'ano':year})
   raw,snapshot=await fetch(url);data=json.loads(raw)['ListaDocumento'];rows=sequence(data.get('documentos',{}).get('documento'))
   if not rows:
    if 'Metadados' not in data:raise ValueError('invalid_empty_feed')
    gaps.append('official_feed_returned_no_records:'+kind+'/'+str(year));continue
   for row in rows:
    item=list_record(row,kind,url,stamp())
    item['catalogue_snapshot']=snapshot
    if item['norm']['year']!=int(year):raise ValueError('feed_year_mismatch')
    before=old.get(norm_key(item),{})
    if before.get('lexml'):item['lexml']=before['lexml']
    records[norm_key(item)]=item
   await wait(.4)
  # Explicit subscriptions bootstrap relevant older acts, not ready-made answers.
  for raw_spec in plan.get('subscriptions',[]):
   spec=Norm.model_validate(raw_spec)
   if spec.kind not in KINDS:continue
   url=f'https://legis.senado.leg.br/dadosabertos/legislacao/{spec.kind}/{spec.number}/{spec.year}.json'
   try:
    raw,snapshot=await fetch(url);docs=sequence(json.loads(raw)['DetalheDocumento']['documentos']['documento'])
    if len(docs)!=1:raise ValueError('subscription_ambiguous')
    doc=docs[0];ident=doc['identificacao'];urn=validated_identity(ident,spec)
    item=list_record({**ident,'ementa':doc.get('ementa','')},spec.kind,url,stamp())
    item['catalogue_snapshot']=snapshot
    if item['urn']!=urn:raise ValueError('subscription_identity_mismatch')
    if old.get(norm_key(item),{}).get('lexml'):item['lexml']=old[norm_key(item)]['lexml']
    records[norm_key(item)]=item
   except (httpx.HTTPError,ValueError,KeyError,TypeError):gaps.append('subscription_unavailable:'+str(spec.number)+'/'+str(spec.year))
   await wait(.4)
  rules=None
  try:
   raw,policy=await fetch(ROBOT);rules=RobotsRules(raw.decode('utf8'))
   # Never use the disallowed /busca/SRU or follow a security challenge.
   policy['role']='provider_access_policy_not_legal_evidence'
  except (httpx.HTTPError,ValueError):gaps.append('lexml_access_policy_unavailable')
  subscribed={(r['kind'],r['number'],r['year']) for r in plan.get('subscriptions',[])}
  # Rotate the oldest attempts. A failed record is retried next daily cycle;
  # there is no rapid retry loop against an unavailable public service.
  ordered=sorted(records.values(),key=lambda r:(r.get('lexml',{}).get('attempted_at',''),0 if norm_key(r) in subscribed else 1,-r['norm']['year'],-r['norm']['number']))
  for item in ordered[:lexml_limit] if rules else []:
   url=item['lexml_source']
   if not rules.can_fetch(AGENT,url):gaps.append('lexml_path_disallowed');break
   # robots currently asks for five seconds. Honor a larger advertised delay.
   delays=[float(x) for x in re.findall(r'(?im)^crawl-delay:\s*(\d+(?:\.\d+)?)',raw.decode('utf8'))]
   await wait(max([5,*delays]));attempted=stamp()
   try:
    body,snapshot=await fetch(url);parsed=parse_lexml(body.decode('utf8'),item['urn'])
    item['lexml']={**parsed,'status':'retrieved','attempted_at':attempted,'retrieved_at':snapshot['retrieved_at'],'snapshot':snapshot}
   except (httpx.HTTPError,ValueError,KeyError,TypeError):
    item['lexml']={**item.get('lexml',{}),'status':'unavailable_last_attempt','attempted_at':attempted};gaps.append('lexml_record_unavailable:'+item['urn'])
  return publish(root,list(records.values()),plan,snapshots,attempts,gaps)

def publish(root,records,plan,snapshots,attempts,gaps):
 if not records:raise ValueError('empty_catalogue_not_published')
 records.sort(key=norm_key);payload=json.dumps(records,ensure_ascii=False,sort_keys=True).encode();now=stamp()
 version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')+'-'+digest(payload)[:10];folder=root/'versions'/version;folder.mkdir(parents=True)
 (folder/'records.json').write_bytes(payload)
 with sqlite3.connect(folder/'catalog.sqlite') as db:
  db.execute('CREATE TABLE norms(id INTEGER PRIMARY KEY,kind TEXT,number INTEGER,year INTEGER,payload TEXT)')
  db.execute("CREATE VIRTUAL TABLE norm_fts USING fts5(search,tokenize='unicode61 remove_diacritics 2')")
  for row in records:
   kind,number,year=norm_key(row)
   cursor=db.execute('INSERT INTO norms(kind,number,year,payload) VALUES(?,?,?,?)',(kind,number,year,json.dumps(row,ensure_ascii=False)))
   text=' '.join([row['name'],row['summary'],row['aliases'],str(number),str(year),row.get('lexml',{}).get('description',''),' '.join(row.get('lexml',{}).get('aliases',[]))])
   db.execute('INSERT INTO norm_fts(rowid,search) VALUES(?,?)',(cursor.lastrowid,text))
  if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('catalogue_integrity_failed')
 counts={'metadata_records':len(records),'lexml_retrieved':sum(r.get('lexml',{}).get('status')=='retrieved' for r in records),'jsonld_legislation':sum(r.get('lexml',{}).get('format')=='jsonld_legislation' for r in records),'labelled_html':sum(r.get('lexml',{}).get('format')=='labelled_html' for r in records)}
 manifest={'version':version,'published':True,'collected_at':now,'coverage':'federal_partial_configured_feeds_and_subscriptions','coverage_complete':False,'plan':plan,'counts':counts,'records_sha256':digest(payload),'snapshots':snapshots,'attempts':attempts,'gaps':gaps,'notice':NOTICE,'normative_text':False,'legal_conclusion_allowed':False}
 (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
 pointer=root/'CURRENT.pending';pointer.write_text(version);pointer.replace(root/'CURRENT')
 return manifest

def export(root=None):
 root=Path(root) if root else root_dir();found=current(root)
 if not found:raise FileNotFoundError('lexml_catalogue_unavailable')
 folder,manifest=found;raw=(folder/'records.json').read_bytes()
 if digest(raw)!=manifest['records_sha256']:raise ValueError('catalogue_integrity_failed')
 items=json.loads(raw);snapshots={s['sha256']:s for s in manifest['snapshots']}
 for row in items:
  if row.get('catalogue_snapshot'):s=row['catalogue_snapshot'];snapshots[s['sha256']]=s
  if row.get('lexml',{}).get('snapshot'):s=row['lexml']['snapshot'];snapshots[s['sha256']]=s
 for s in snapshots.values():
  compressed=(root/'snapshots'/(s['sha256']+'.gz')).read_bytes()
  if digest(gzip.decompress(compressed))!=s['sha256']:raise ValueError('source_integrity_failed')
  s['snapshot_gzip_base64']=base64.b64encode(compressed).decode()
 return {'manifest':manifest,'items':items,'snapshots':list(snapshots.values()),'notice':NOTICE}

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--plan',required=True);parser.add_argument('--lexml-limit',type=int,default=30);args=parser.parse_args()
 if not 1<=args.lexml_limit<=100:parser.error('lexml-limit must be 1..100')
 try:
  manifest=asyncio.run(harvest(args.root,json.loads(Path(args.plan).read_text()),args.lexml_limit));print(json.dumps({k:manifest[k] for k in ('version','counts','collected_at','gaps')},ensure_ascii=True))
 except (httpx.HTTPError,ValueError,KeyError,TypeError) as e:
  # The previous CURRENT survives. Only public collection diagnostics here.
  Path(args.root,'last_failure.json').write_text(json.dumps({'at':stamp(),'failure':type(e).__name__,'previous_version_preserved':True}));raise
