import pathlib,subprocess,json,shutil
root=pathlib.Path(__file__).resolve().parents[2];tag='moara-core:legal-metadata-20261031'
for service,base in [('ai-server-moara-gateway-1','moara-core:pre-legal-metadata-app-20261031'),('ai-server-moara-legal-mcp-1','moara-core:pre-legal-metadata-mcp-20261031')]:
 if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:
  image=subprocess.check_output(['docker','inspect',service,'--format','{{.Image}}'],text=True).strip();subprocess.run(['docker','tag',image,base],check=True)
folder=root/'tmp/legal-metadata-build';folder.mkdir(exist_ok=True);dockerfile='FROM moara-core:pre-legal-metadata-app-20261031\n'
for name in ['moara/legal_mcp/lexml_catalog.py','moara/legal_mcp/discovery.py','moara/legal_mcp/web_recovery.py','moara/legal_mcp/server.py','moara/gateway/api.py','moara/gateway/lexml_catalog_api.py','moara/research_browser/policy.py']:
 target=folder/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/name,target);dockerfile+='COPY '+name+' /app/'+name+'\n'
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True);dockerfile+='COPY web /app/web\n';(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/stf-catalog-build/tests',tests,dirs_exist_ok=True)
for name in ['test_lexml_catalog.py','test_legal_catalog.py']:shutil.copyfile(root/'moara/tests'/name,tests/name)
subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=64m','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],check=True)
source=(root/'infrastructure/legal/stage_grounding.py').read_text().replace('moara-core:legal-grounding-20261031',tag).replace('moara-legal-grounding-stage-','moara-legal-metadata-mcp-stage-').replace('moara-legal-app-grounding-stage-','moara-legal-metadata-app-stage-').replace('tmp/legal-grounding-stage.json','tmp/legal-metadata-stage.json')
source=source.replace("args+=[image]+original['Config']['Cmd'];", "args+=['--mount',f'type=bind,src={root}/data/legal/stf-theses,dst=/app/legal_catalog/stf,readonly','--mount',f'type=bind,src={root}/data/legal/metadata,dst=/app/legal_catalog/lexml,readonly'];args+=[image]+original['Config']['Cmd'];")
exec(compile(source,'stage_legal_metadata','exec'),{'__file__':str(root/'infrastructure/legal/stage_grounding.py')})
