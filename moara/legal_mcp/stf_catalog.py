"""Versioned public STF thesis catalogue. A snapshot is not a current merits certificate."""
import argparse,asyncio,hashlib,json,os,re,sqlite3,gzip,time,base64
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode,quote
import httpx
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from .sources import clean
from moara.research_browser.policy import robot_policy

PORTAL='https://portal.stf.jus.br/repercussaogeral/teses.asp'
ENDPOINT='https://portal.stf.jus.br/repercussaogeral/retornartesesrepercussaogeral.asp'
SCRIPT='https://portal.stf.jus.br/scripts/tesesrepercussaogeral.js'
ROBOT='https://portal.stf.jus.br/robots.txt'
AGENT='Moara-LegalCatalog/0.1'
NOTICE='Acervo de teses divulgadas pelo STF. A divulgação pode anteceder a publicação do acórdão. Ausência de repercussão geral não equivale a tese de mérito constitucional. A coleta não confirma recursos, trânsito em julgado ou modulação; temas com mérito pendente podem não constar destes bancos.'

class CatalogSearch(BaseModel):
 model_config=ConfigDict(extra='forbid')
 query:str=Field(default='',max_length=160)
 bank:Literal['all','com','sem']='all'
 theme:int|None=Field(default=None,ge=1,le=99999)
 page:int=Field(default=1,ge=1,le=2000)
 limit:int=Field(default=20,ge=1,le=50)

def decode_bank(raw,bank):
 rows=json.loads(raw)
 if not isinstance(rows,list) or not 1<=len(rows)<=30000:raise ValueError('incomplete_or_invalid_bank')
 items=[]
 for row in rows:
  if not isinstance(row,dict):raise ValueError('invalid_thesis_record')
  number=str(row.get('numeroTema','')).strip();text=clean(row.get('descricaoTese',''))
  if not number.isdigit() or not 1<=int(number)<=99999 or len(text)<15:raise ValueError('invalid_thesis_identity_or_text')
  classe=str(row.get('siglaClasse','')).strip();process=str(row.get('numeroProcesso','')).strip();incident=str(row.get('incidente','')).strip()
  valid_case=bool(re.fullmatch(r'[A-Z]{1,12}',classe) and process.isdigit() and incident.isdigit())
  source='https://portal.stf.jus.br/jurisprudenciaRepercussao/tema.asp?num='+str(int(number))
  movement='https://portal.stf.jus.br/jurisprudenciaRepercussao/verAndamentoProcesso.asp?'+urlencode({'incidente':incident,'numeroProcesso':process,'classeProcesso':classe,'numeroTema':str(int(number))}) if valid_case else None
  acordao='https://jurisprudencia.stf.jus.br/pages/search?'+urlencode({'classeNumeroIncidente':classe+' '+process,'base':'acordaos','sinonimo':'true','plural':'true','page':1,'pageSize':10,'sort':'_score','sortBy':'desc','isAdvanced':'true','origem':'AP'}) if valid_case else None
  items.append({'theme':int(number),'bank':bank,'thesis_text':text,'leading_case':classe+' '+process if valid_case else None,'incident':incident if valid_case else None,'displayed_event_date':str(row.get('dataAndamento','')),'source':source,'andamento_url':movement,'acordao_search_url':acordao,'catalog_source':PORTAL,'record_sha256':hashlib.sha256(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()})
 return items

def root_dir():return Path(os.getenv('MOARA_STF_CATALOG_DIR','/app/legal_catalog/stf'))

def current(root=None):
 root=Path(root) if root else root_dir()
 try:
  version=(root/'CURRENT').read_text().strip()
  if not re.fullmatch(r'[A-Za-z0-9_-]{8,100}',version):return None
  folder=(root/'versions'/version).resolve()
  if not folder.is_relative_to((root/'versions').resolve()):return None
  manifest=json.loads((folder/'manifest.json').read_text())
  if manifest.get('complete') is not True or not (folder/'catalog.sqlite').is_file():return None
  return folder,manifest
 except (OSError,ValueError):return None

def search(spec,root=None):
 found=current(root);empty={'available':False,'items':[],'total':0,'page':spec.page,'limit':spec.limit,'notice':NOTICE,'legal_conclusion_allowed':False,'freshly_rechecked':False}
 if not found:return empty
 folder,manifest=found;where=[];params=[]
 if spec.bank!='all':where.append('t.bank=?');params.append(spec.bank)
 if spec.theme:where.append('t.theme=?');params.append(spec.theme)
 # FTS is local and parameterized. User input never becomes SQL syntax or a URL.
 stop={'qual','quais','tema','temas','stf','sobre','trata','com','sem','repercussao','repercussão','geral','que','pessoas','tem','direito','uma','para','dos','das','lei','leis'}
 terms=[t for t in re.findall(r'[^\W_]+',spec.query.casefold(),re.UNICODE) if len(t)>1 and t not in stop][:12]
 offset=(spec.page-1)*spec.limit
 with sqlite3.connect('file:'+quote(str(folder/'catalog.sqlite'))+'?mode=ro',uri=True) as db:
  db.row_factory=sqlite3.Row
  join=''
  if terms:
   join=' JOIN thesis_fts f ON f.rowid=t.id';where.append('thesis_fts MATCH ?');params.append(' AND '.join('"'+t+'"' for t in terms))
  suffix=(' WHERE '+' AND '.join(where)) if where else ''
  total=db.execute('SELECT count(*) FROM theses t'+join+suffix,params).fetchone()[0]
  order=' ORDER BY bm25(thesis_fts),t.theme,t.bank' if terms else ' ORDER BY t.theme,t.bank'
  rows=db.execute('SELECT t.payload FROM theses t'+join+suffix+order+' LIMIT ? OFFSET ?',[*params,spec.limit,offset]).fetchall()
 return {'available':True,'items':[json.loads(r['payload']) for r in rows],'total':total,'page':spec.page,'limit':spec.limit,'version':manifest['version'],'collected_at':manifest['collected_at'],'source_updated_label':manifest.get('source_updated_label'),'counts':manifest['counts'],'notice':NOTICE,'legal_conclusion_allowed':False,'freshly_rechecked':False}

def export(root=None):
 found=current(root)
 if not found:raise FileNotFoundError('stf_catalog_not_collected')
 folder,manifest=found
 for snapshot in manifest['snapshots']:
  digest=snapshot['sha256']
  if not re.fullmatch(r'[a-f0-9]{64}',digest):raise ValueError('invalid_snapshot_identity')
  path=(folder/(digest+'.gz')).resolve()
  if not path.is_relative_to(folder.resolve()):raise ValueError('invalid_snapshot_path')
  compressed=path.read_bytes();raw=gzip.decompress(compressed)
  if len(raw)!=snapshot['bytes'] or hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('catalog_snapshot_integrity_failed')
  snapshot['snapshot_gzip_base64']=base64.b64encode(compressed).decode()
 return {'manifest':manifest,'items':json.loads((folder/'records.json').read_text())['items'],'notice':NOTICE,'freshly_rechecked':False}

async def harvest(root):
 root=Path(root);observed=datetime.now(timezone.utc).isoformat();snapshots=[]
 async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=45) as client:
  async def fetch(url,bank=None):
   r=await (client.post(url,data={'tipo':bank},headers={'User-Agent':AGENT}) if bank else client.get(url,headers={'User-Agent':AGENT}));r.raise_for_status()
   if len(r.content)>8*1024**2:raise ValueError('catalog_response_too_large')
   raw=r.content;snapshots.append((raw,{'url':url,'method':'POST' if bank else 'GET','form':{'tipo':bank} if bank else None,'retrieved_at':datetime.now(timezone.utc).isoformat(),'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'content_type':r.headers.get('content-type'),'bank':bank}))
   await asyncio.sleep(.7);return raw
  robots=await fetch(ROBOT);rules,_=robot_policy(robots)
  for url in [PORTAL,SCRIPT,ENDPOINT]:
   if not rules.can_fetch(AGENT,url):raise ValueError('official_source_disallows_collection')
  page=await fetch(PORTAL);script=await fetch(SCRIPT)
  if b'retornartesesrepercussaogeral.asp' not in script or b'array.slice' not in script:raise ValueError('official_collection_contract_changed')
  banks={bank:decode_bank(await fetch(ENDPOINT,bank),bank) for bank in ('com','sem')}
 items=sorted(banks['com']+banks['sem'],key=lambda row:(row['theme'],row['bank'],row['record_sha256']))
 source_updated=re.search(r'Última Atualização:\s*([^<\r\n]+)',page.decode('utf-8',errors='replace'))
 version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+hashlib.sha256(b''.join(raw for raw,_ in snapshots)).hexdigest()[:12]
 folder=root/'versions'/version;folder.mkdir(parents=True,exist_ok=False)
 for raw,metadata in snapshots:
  filename=metadata['sha256']+'.gz';(folder/filename).write_bytes(gzip.compress(raw,mtime=0));metadata['snapshot_file']=filename
 (folder/'records.json').write_text(json.dumps({'items':items},ensure_ascii=False,indent=2),encoding='utf-8')
 with sqlite3.connect(folder/'catalog.sqlite') as db:
  db.executescript("CREATE TABLE theses(id INTEGER PRIMARY KEY,theme INTEGER NOT NULL,bank TEXT NOT NULL,payload TEXT NOT NULL); CREATE INDEX themes_bank ON theses(theme,bank); CREATE VIRTUAL TABLE thesis_fts USING fts5(theme,thesis,leading_case,tokenize='unicode61 remove_diacritics 2');")
  for row in items:
   cursor=db.execute('INSERT INTO theses(theme,bank,payload) VALUES(?,?,?)',(row['theme'],row['bank'],json.dumps(row,ensure_ascii=False)))
   db.execute('INSERT INTO thesis_fts(rowid,theme,thesis,leading_case) VALUES(?,?,?,?)',(cursor.lastrowid,str(row['theme']),row['thesis_text'],row['leading_case'] or ''))
  assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 counts={bank:len(rows) for bank,rows in banks.items()};numbers={bank:{r['theme'] for r in rows} for bank,rows in banks.items()}
 manifest={'complete':True,'version':version,'collected_at':observed,'source':PORTAL,'source_updated_label':source_updated[1].strip() if source_updated else None,'counts':counts,'total':len(items),'unique_themes':len(numbers['com']|numbers['sem']),'themes_in_both_banks':sorted(numbers['com']&numbers['sem']),'snapshots':[metadata for _,metadata in snapshots],'pagination':'portal_downloads_each_bank_once_and_paginates_the_complete_array_in_browser','notice':NOTICE}
 (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
 root.mkdir(exist_ok=True,parents=True);temporary=root/('CURRENT-'+version);temporary.write_text(version);os.replace(temporary,root/'CURRENT')
 return manifest

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);args=parser.parse_args()
 print(json.dumps(asyncio.run(harvest(args.root)),ensure_ascii=True))
