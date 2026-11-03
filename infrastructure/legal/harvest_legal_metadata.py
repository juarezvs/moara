"""Isolated public collector, invoked by a user systemd timer. No model or secrets."""
import pathlib,subprocess,fcntl,sys
root=pathlib.Path(__file__).resolve().parents[2];target=root/'data/legal/metadata';target.mkdir(parents=True,exist_ok=True)
with (target/'worker.lock').open('w') as lock:
 try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('Collection already running');sys.exit(0)
 image=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()
 args=['docker','run','--rm','--name','moara-metadata-collector','--user','0:0','--network','ai-server_moara_legal_egress','--read-only','--tmpfs','/tmp:size=64m','--memory','512m','--cpus','1','--pids-limit','64','--cap-drop','ALL','--security-opt','no-new-privileges:true','-v',str(root/'moara/legal_mcp/lexml_catalog.py')+':/app/moara/legal_mcp/lexml_catalog.py:ro','-v',str(root/'moara/infrastructure/legal-metadata-plan.json')+':/plan.json:ro','-v',str(root/'moara/research_browser/policy.py')+':/app/moara/research_browser/policy.py:ro','-v',str(target)+':/catalog','--entrypoint','python',image,'-m','moara.legal_mcp.lexml_catalog','--root','/catalog','--plan','/plan.json','--lexml-limit',sys.argv[1] if len(sys.argv)>1 else '30']
 subprocess.run(args,check=True,timeout=1500)
