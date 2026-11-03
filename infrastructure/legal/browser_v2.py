"""Legal verification through real chat, protected evidence and session ACLs."""
import sys,json,hashlib
from pathlib import Path
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
fixture=json.loads(sys.stdin.readline());checks={};chats=[];errors=[];evidence_ids=[]
output=Path('/artifacts/legal-sources-v2-ui.json')
def proxy(route):
    u=urlsplit(route.request.url)
    r=route.fetch(url='http://'+fixture['candidate']+':8075'+u.path.removeprefix('/moara')+('?' +u.query if u.query else ''),max_redirects=0,timeout=180000)
    route.fulfill(response=r)
def configure(context):
    if fixture.get('candidate'):context.route('https://moara.am.trf1.gov.br/moara/**',proxy)
def checkpoint(context):
    token=next((c['value'] for c in context.cookies() if c['name']=='__Secure-moara_session'),None)
    output.write_text(json.dumps({'checks':checks,'created_chats':chats,'evidence_ids':evidence_ids,
        'test_session_sha256':hashlib.sha256(token.encode()).hexdigest() if token else None,'javascript_errors':errors}))
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True,chromium_sandbox=True,args=['--disable-dev-shm-usage','--ignore-certificate-errors-spki-list='+fixture['spki']])
    context=browser.new_context(viewport={'width':1600,'height':1100});configure(context)
    context.add_init_script("if(window===window.top&&location.origin==='https://moara.am.trf1.gov.br')localStorage.setItem('token',"+json.dumps(fixture['token'])+");")
    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)[:160]))
    def seen(r):
        if r.request.method=='POST' and r.status==201 and r.url.endswith('/moara/api/v1/chats'):
            chats.append(r.json()['id']);checkpoint(context)
    page.on('response',seen)
    try:
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
        expect(page.locator('.context-row')).to_have_count(5,timeout=45000);checkpoint(context)
        page.get_by_role('tab',name='Referências',exact=True).click()
        page.locator('input[name=reference-norm]').fill('Lei 14.133/2021')
        page.locator('input[name=reference-article]').fill('art. 6')
        page.locator('input[name=reference-date]').fill(fixture['today'])
        page.get_by_role('button',name='Conferir fontes oficiais',exact=True).click()
        link=page.get_by_role('link',name='Consultar evidências e fontes',exact=True)
        expect(link).to_be_visible(timeout=180000)
        expect(page.locator('.moara-processing')).not_to_be_visible(timeout=30000)
        answer=page.locator('.message:not(.user-message) .markdown').last
        expect(answer).to_contain_text('Histórico legislativo complementar — Câmara dos Deputados')
        expect(answer).to_contain_text('PL 6814/2017');expect(answer).to_contain_text('vigência não confirmada')
        checks['native_chat_uses_new_camara_provenance']=True
        checks['official_wording_and_version_dates_in_answer']='Versão textual datada de' in answer.inner_text()
        checks['related_norms_reported']='Normas correlatas com identificação e publicações recuperadas' in answer.inner_text()
        href=link.get_attribute('href');evidence_ids.append(href.rsplit('/',1)[-1]);checkpoint(context)
        value=page.evaluate("async url=>{const r=await fetch(url,{headers:{Accept:'application/json'}});if(!r.ok)throw new Error('Evidence read failed');return r.json();}",href)
        checks['encrypted_evidence_manifest_integrity']=value['integrity']=='stored_manifest_verified'
        checks['replay_is_not_new_verification']=value['rechecked_now'] is False
        package=value['verification'];norm=package['norms'][0]
        checks['schema2_with_official_sources']=package['schema_version']==2 and norm['legislative_history']['status']=='legislative_history_retrieved'
        checks['no_uncertified_legal_conclusion']=package['legal_conclusion_allowed'] is False
        checks['public_manifest_omits_source_binaries']=all('snapshot_gzip_base64' not in s for s in norm['snapshots'])
        replay=page.evaluate("""async url=>{const v=await(await fetch(url+'?download=true')).json();let count=0;for(const norm of v.verification.norms)for(const s of norm.snapshots){const compressed=Uint8Array.from(atob(s.snapshot_gzip_base64),c=>c.charCodeAt(0));const raw=await new Response(new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer();const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),b=>b.toString(16).padStart(2,'0')).join('');if(digest!==s.sha256)return {ok:false};count++;}return {ok:count>0,count};}""",href)
        checks['downloaded_source_hashes_reproduce']=replay['ok'];checks['source_snapshot_count']=replay['count']
        page.goto('https://moara.am.trf1.gov.br'+href,wait_until='domcontentloaded')
        expect(page.get_by_role('heading',name='Evidências da conferência jurídica')).to_be_visible()
        expect(page.get_by_role('heading',name='Histórico legislativo complementar — Câmara dos Deputados')).to_be_visible()
        checks['evidence_page_displays_new_history_and_checks']=True
        anonymous=browser.new_context();configure(anonymous);a=anonymous.new_page()
        r=a.goto('https://moara.am.trf1.gov.br'+href,wait_until='domcontentloaded')
        checks['evidence_not_public']=r.status in (401,403,404);anonymous.close()
        page.goto('https://moara.am.trf1.gov.br/moara/chat',wait_until='domcontentloaded')
        expect(page.get_by_label('Sua mensagem',exact=True)).to_be_visible(timeout=30000)
        page.get_by_label('Sua mensagem',exact=True).fill('quais suas habilidades?')
        page.get_by_role('button',name='Enviar solicitação',exact=True).click()
        answer=page.locator('.message:not(.user-message) .markdown').last
        expect(answer).to_contain_text('Moara',timeout=60000)
        checks['ordinary_chat_remains_available']='informe a data relevante' not in answer.inner_text().lower()
        checks['no_javascript_errors']=not errors
    finally:
        try:
            checks['synthetic_chat_archived']=page.evaluate("""async ids=>{const me=await(await fetch('/moara/api/v1/auth/me')).json();let ok=true;for(const id of ids){const r=await fetch('/moara/api/v1/chats/'+id+'/archive',{method:'POST',headers:{'X-Moara-CSRF':me.csrf_token}});ok=ok&&r.ok;}return ok;}""",chats)
        finally:checkpoint(context);context.close();browser.close()
print(json.dumps({'checks':checks,'errors':errors}));assert checks and all(checks.values())
