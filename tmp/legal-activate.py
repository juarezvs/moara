import pathlib,subprocess,json,base64,os
root=pathlib.Path('/home/nutec/ai-server')
backup=root/'backups/legal-20261030';backup.mkdir(mode=0o700,exist_ok=True)
compose=root/'moara/infrastructure/scripts/compose.sh'
saved=backup/'compose.sh'
if not saved.exists():saved.write_bytes(compose.read_bytes())
for name,value in json.loads((root/'tmp/legal-original-sources.json').read_text()).items():
    target=backup/name
    if not target.exists():target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(base64.b64decode(value))
new=(root/'tmp/legal-compose-wrapper.sh').read_bytes().replace(b'\r\n',b'\n')
compose.write_bytes(new);compose.chmod(0o755)
cmd=['sh',str(compose)]
subprocess.run(cmd+['config','--quiet'],check=True)
subprocess.run(cmd+['up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','120','moara-gateway','moara-legal-mcp'],check=True)
print('LEGAL_CONFERENCE_PRODUCTION_ACTIVE',flush=True)
