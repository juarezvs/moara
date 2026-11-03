"""Real TLS uploads over a throttled connection; no response interception."""
import sys,json,hashlib,re,uuid
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};resources=[];errors=[];network_errors=[];upload_responses=[]
output=Path('/artifacts/unified-ui.json');stage=bool(fixture.get('candidate_ip'))
file=Path('/tmp/upload-qa-'+uuid.uuid4().hex[:10]+'.pdf')
with file.open('wb') as f:
 f.write(b'%PDF-1.4\n');offsets=[0]
 objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 600 600] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
 text=b'BT /F1 12 Tf 30 550 Td (Public synthetic upload verification. Marker UPLOAD_QA_COMPLETE.) Tj ET'
 objects.append(b'<< /Length '+str(len(text)).encode()+b' >>\nstream\n'+text+b'\nendstream')
 for n,body in enumerate(objects,1):offsets.append(f.tell());f.write(str(n).encode()+b' 0 obj\n'+body+b'\nendobj\n')
 offsets.append(f.tell());f.write(b'6 0 obj\n<< /Length 41943040 >>\nstream\n')
 for _ in range(40):f.write(b'x'*1024**2)
 f.write(b'\nendstream\nendobj\n');xref=f.tell();f.write(b'xref\n0 7\n0000000000 65535 f \n')
 for pos in offsets[1:]:f.write(('%010d 00000 n \n'%pos).encode())
 f.write(b'trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n'+str(xref).encode()+b'\n%%EOF\n')
digest=hashlib.sha256(file.read_bytes()).hexdigest()
def checkpoint(context):
 cookie=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
 output.write_text(json.dumps({'checks':checks,'created_chats':[],'created_resources':resources,'javascript_errors':errors,'network_errors':network_errors,'upload_responses':upload_responses,'test_session_sha256':hashlib.sha256(cookie.encode()).hexdigest() if cookie else None,'bytes':file.stat().st_size}))
with sync_playwright() as p:
 args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']]
 if stage:args+=['--host-resolver-rules=MAP moara.am.trf1.gov.br '+fixture['candidate_ip'],'--no-proxy-server']
 browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=args)
 context=browser.new_context(viewport={'width':1500,'height':950},timezone_id='America/Manaus')
 context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
 page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
 def response(r):
  if r.request.method=='POST' and urlsplit(r.url).path.endswith('/platform/documents/upload'):
   upload_responses.append({'status':r.status});checkpoint(context)
 page.on('response',response)
 page.on('requestfailed',lambda r:network_errors.append(r.failure) if urlsplit(r.url).path.endswith('/platform/documents/upload') else None)
 try:
  page.goto('https://moara.am.trf1.gov.br/moara/'+('espaco' if stage else 'chat'),wait_until='domcontentloaded')
  if stage:expect(page.get_by_label('Adicionar documento',exact=True)).to_be_visible(timeout=45000)
  else:
   expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=45000)
   page.locator('.work-nav').get_by_role('tab',name='Documentos',exact=True).click()
  checkpoint(context)
  page.evaluate("""()=>{window.__uploadValues=[];window.__uploadPhases=[];new MutationObserver(()=>{const e=document.querySelector('moara-upload-progress progress');if(e){window.__uploadValues.push(e.value);window.__uploadPhases.push(document.querySelector('moara-upload-progress p')?.textContent||'');}}).observe(document.body,{attributes:true,childList:true,subtree:true,characterData:true});}""")
  cdp=context.new_cdp_session(page);cdp.send('Network.enable');cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':20,'downloadThroughput':50*1024**2,'uploadThroughput':4*1024**2,'connectionType':'ethernet'})
  (page.get_by_label('Adicionar documento',exact=True) if stage else page.locator('.document-dropzone input[type=file]')).set_input_files(str(file))
  page.wait_for_function('()=>{const p=document.querySelector("moara-upload-progress progress");return p&&p.value>0&&p.value<100}',timeout=30000)
  checks['actual_intermediate_percent_is_visible']=True
  page.wait_for_function('()=>new Set(window.__uploadValues.filter(v=>v>0&&v<100)).size>=2',timeout=30000)
  page.screenshot(path='/artifacts/document-upload-progress.png',mask=[page.locator('.history-items'),page.locator('.work-user'),page.locator('.document-list'),page.locator('.platform-list')],mask_color='#162d3e')
  cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
  page.wait_for_function('()=>{const s=document.querySelector("moara-upload-progress p")?.textContent||"";return s.includes("armazenado")||s.includes("pronto")||s.includes("Extraindo o texto")||s.includes("erro");}',timeout=120000)
  rows=page.evaluate("async()=>await(await fetch('/moara/api/v1/platform/resources?kind=document')).json()")
  resources.extend(row['id'] for row in rows if row['title']==file.name);checkpoint(context)
  expect(page.locator('moara-upload-progress p')).to_contain_text('Arquivo armazenado' if stage else 'Documento pronto',timeout=480000)
  checks['large_file_above_32_mib_is_accepted']=bool(resources) and file.stat().st_size>32*1024**2
  checks['upload_reaches_one_hundred_percent']=page.locator('moara-upload-progress progress').evaluate('(e)=>e.value===100')
  values=page.evaluate('window.__uploadValues');checks['progress_is_measured_in_multiple_steps']=len(set(v for v in values if 0<v<100))>=2
  checks['confirmation_is_distinct_from_transfer']=any('Confirmando armazenamento' in text for text in page.evaluate('window.__uploadPhases'))
  if not stage:
   checks['indexing_is_a_separate_phase']=any('Extraindo o texto' in text for text in page.evaluate('window.__uploadPhases'))
   checks['indexed_document_is_selected']=page.locator('.document-item').filter(has_text=file.name).locator('input').is_checked()
   record=page.evaluate('async(id)=>await(await fetch("/moara/api/v1/platform/documents/"+id+"/chunks")).json()',resources[-1])
   checks['real_text_is_indexed']='UPLOAD_QA_COMPLETE' in ' '.join(c['text'] for c in record)
  result=page.evaluate("""async(id)=>{const r=await fetch('/moara/api/v1/platform/documents/'+id+'/download');const data=await r.arrayBuffer();return {status:r.status,sha256:Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),v=>v.toString(16).padStart(2,'0')).join('')};}""",resources[-1])
  checks['download_matches_original_bytes']=result['status']==200 and result['sha256']==digest
  checks['four_mib_message_is_absent']='4 MiB' not in page.locator('body').inner_text()
  checks['no_javascript_errors']=not errors
 finally:
  try:
   checks['synthetic_documents_archived']=page.evaluate("""async(ids)=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of ids){const row=await(await fetch('/moara/api/v1/platform/resources/'+id)).json();const r=await fetch('/moara/api/v1/platform/resources/'+id+'/archive',{method:'POST',headers:{'Content-Type':'application/json','X-Moara-CSRF':me.csrf_token},body:JSON.stringify({version:row.version})});ok=ok&&r.ok;}return ok;}""",resources)
  finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'bytes':file.stat().st_size}));assert checks and all(checks.values()),checks
