"""Allow 32 MB chat file uploads while preserving all other proxy limits."""
from pathlib import Path
import subprocess, shutil
root=Path('/home/nutec/ai-server')
path=root/'infrastructure/caddy/Caddyfile'
marker='  @chat_upload {'
block="""  @chat_upload {
    method POST
    path /api/v1/files /api/v1/files/
  }
  handle @chat_upload {
    request_body {
      max_size 32MB
    }
    reverse_proxy webui:8080
  }

"""
source=path.read_text()
anchor='  handle {\n    request_body {\n      max_size 2MB\n    }\n    reverse_proxy webui:8080\n  }'
assert source.count(anchor)==1, 'Unexpected Caddy fallback; inspect before patching'
if marker not in source:
 backup=root/'docs/runtime/upload-json-20261027'
 backup.mkdir(parents=True,exist_ok=True)
 shutil.copy2(path,backup/'Caddyfile.before')
 path.write_text(source.replace(anchor,block+anchor))
 try:
  subprocess.run(['docker','exec','ai-server-caddy-1','caddy','validate','--config','/etc/caddy/Caddyfile'],check=True,capture_output=True)
  subprocess.run(['docker','restart','ai-server-caddy-1'],check=True,capture_output=True)
 except Exception:
  path.write_text(source)
  subprocess.run(['docker','restart','ai-server-caddy-1'],capture_output=True)
  raise
else:
 assert block in source
print('Chat upload limit: 32 MB; fallback: 2 MB; Caddy validated and restarted.')
