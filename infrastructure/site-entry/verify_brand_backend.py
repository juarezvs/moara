"""Compare real running backend files; the release changes web assets only."""
import json,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[2]
candidate=(root/'tmp/brand-core-name.txt').read_text().strip()
script="""from pathlib import Path
import hashlib
h=hashlib.sha256()
for name in ['gateway','legal_mcp','identity','assistants']:
 root=Path('/app/moara')/name
 for p in sorted(root.rglob('*')):
  if p.is_file() and '__pycache__' not in str(p):h.update(str(p.relative_to('/app')).encode()+b'\\0'+hashlib.sha256(p.read_bytes()).digest())
print(h.hexdigest())
"""
def checksum(name):return subprocess.check_output(['docker','exec',name,'python','-c',script],text=True).strip()
baseline=checksum('ai-server-moara-gateway-1');result=checksum(candidate)
value={'backend_unchanged':baseline==result,'baseline_sha256':baseline,'candidate_sha256':result,
 'baseline_image':subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip(),
 'candidate_image':subprocess.check_output(['docker','inspect',candidate,'--format','{{.Image}}'],text=True).strip()}
(root/'docs/runtime/brand-backend-preservation.json').write_text(json.dumps(value,indent=2))
print(json.dumps(value));assert value['backend_unchanged']
