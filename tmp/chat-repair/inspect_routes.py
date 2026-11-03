import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
print(source(r'''docker exec -i ai-server-webui-1 python - <<'PY'
from pathlib import Path
p=Path('/app/backend/open_webui/routers/chats.py')
print('CHAT_ROUTER_EXISTS',p.exists())
if p.exists():
 for line in p.read_text().splitlines():
  if '@router.' in line and ('archive' in line or 'new' in line):print(line.strip())
p=Path('/app/backend/open_webui/routers/files.py')
if p.exists():
 for line in p.read_text().splitlines():
  if '@router.' in line and ('status' in line or '"/"' in line or "'/'" in line):print(line.strip())
PY
'''))
