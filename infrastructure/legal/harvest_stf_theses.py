"""One-shot collection with no institutional credentials or database access."""
import pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2];target=root/'data/legal/stf-theses';target.mkdir(parents=True,exist_ok=True)
image=subprocess.check_output(['docker','inspect','ai-server-moara-legal-mcp-1','--format','{{.Image}}'],text=True).strip()
args=['docker','run','--rm','--user','0:0','--network','ai-server_moara_legal_egress','--read-only','--tmpfs','/tmp:size=64m','--memory','512m','--cpus','1','--cap-drop','ALL','--security-opt','no-new-privileges:true','-v',str(root/'moara/legal_mcp/stf_catalog.py')+':/app/moara/legal_mcp/stf_catalog.py:ro','-v',str(target)+':/catalog','--entrypoint','python',image,'-m','moara.legal_mcp.stf_catalog','--root','/catalog']
subprocess.run(args,check=True)
