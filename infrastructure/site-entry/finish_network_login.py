import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2]
image=subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1','--format','{{.Image}}'],text=True).strip()
report=json.loads((root/'docs/runtime/unified-ui-public.json').read_text())
assert report['checks'] and all(report['checks'].values()) and report['tested_image_id']==image
shutil.copyfile(root/'docs/runtime/unified-ui-public.json',root/'docs/runtime/network-login-public.json')
artifacts=root/'infrastructure/site-entry'/('unified-output-'+report['test_container'].rsplit('-',1)[1])
for size in ['mobile','desktop']:
 shutil.copyfile(artifacts/('login-'+size+'.png'),root/'docs/runtime'/('network-login-'+size+'.png'))
for filename in ['README.md','docs/PROJECT_STATUS.md','docs/MOARA_2_OPERATIONS.md']:
 path=root/filename;target=('docs/' if filename=='README.md' else '')+'MOARA_NETWORK_LOGIN_2026-10-31.md'
 if target not in path.read_text():
  with path.open('a') as out:out.write('\n\nLogin de rede: [matricula, senha e orgao]('+target+').\n')
stopped=[]
for name in subprocess.check_output(['docker','ps','--format','{{.Names}}'],text=True).splitlines():
 if name.startswith(('moara-unified-stage-','moara-unified-proxy-stage-')):
  info=json.loads(subprocess.check_output(['docker','inspect',name]))[0];assert not info['HostConfig'].get('PortBindings')
  subprocess.run(['docker','stop',name],check=True,capture_output=True);stopped.append(name)
print(json.dumps({'published':True,'checks_passed':len(report['checks']),'image':image,'stopped_private_candidates':stopped}))
