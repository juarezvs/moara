import pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
from gpu_remote import source
print(source(r'''docker exec -i ai-server-webui-1 python - <<'PY'
from pathlib import Path
p=Path('/app/backend/open_webui/utils/middleware.py');lines=p.read_text().splitlines()
for i,line in enumerate(lines):
 if 'rag_template(' in line or 'apply_context_to_messages' in line:
  print('\n'.join(lines[max(0,i-4):i+13]))
for p in Path('/app/backend/open_webui/utils').glob('*.py'):
 lines=p.read_text().splitlines()
 for i,line in enumerate(lines):
  if 'def update_message_content(' in line:print('\n'.join(lines[i:i+50]))
PY
'''))
