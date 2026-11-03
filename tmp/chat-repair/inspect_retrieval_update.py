import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
print(source(r'''docker exec -i ai-server-webui-1 python - <<'PY'
from pathlib import Path
p=Path('/app/backend/open_webui/routers/retrieval.py');lines=p.read_text().splitlines()
for i,line in enumerate(lines):
 if 'class ConfigForm' in line or "'/config/update'" in line or '"/config/update"' in line:
  print('\n'.join(lines[i:i+85]))
PY
'''))
