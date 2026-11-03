"""Read-only production HTTP/TLS checks without authentication material."""
import pathlib,json,ssl,urllib.request,urllib.error,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
ctx=ssl.create_default_context()
for name in ['ai-root-ca.crt','moara-domain-root-ca.crt']:ctx.load_verify_locations(cafile=str(root/'docs/runtime'/name))
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),NoRedirect())
checks={};responses={}
for method,path in [('GET','/'),('HEAD','/'),('GET','/?q=test'),('GET','/chat-anterior'),('GET','/?interface=anterior'),('GET','/moara/chat'),('GET','/moara/brand/mark.svg'),('GET','/moara/api/v1/ready')]:
 try:r=opener.open(urllib.request.Request('https://moara.am.trf1.gov.br'+path,method=method),timeout=20)
 except urllib.error.HTTPError as e:r=e
 key=method+' '+path
 responses[key]={'status':r.status,'location':r.headers.get('Location'),'cache_control':r.headers.get('Cache-Control')}
 if path=='/' or path=='/?q=test':checks[key]=r.status==302 and r.headers.get('Location')=='/moara/chat' and r.headers.get('Cache-Control')=='no-store'
 elif path=='/chat-anterior':checks[key]=r.status==302 and r.headers.get('Location')=='/?interface=anterior'
 else:checks[key]=r.status==200
 r.close()
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Config.Image}}'],text=True).strip()
checks['expected_image']=image=='moara-core:legal-sources-v2-20261030'
containers=[json.loads(line) for line in subprocess.check_output(['docker','ps','--format','{{json .}}'],text=True).splitlines()]
checks['no_running_unhealthy_services']=not any('(unhealthy)' in c['Status'] for c in containers)
report={'checks':checks,'responses':responses,'image':image,'tls_validation':True}
(root/'docs/runtime/legal-sources-v2-http.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report));assert all(checks.values())
