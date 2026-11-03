import pathlib,subprocess,json,shutil,re,time
root=pathlib.Path(__file__).resolve().parents[2]
tag='moara-core:document-upload-20261102';base='moara-core:pre-document-upload-20261102'
original=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
if subprocess.run(['docker','image','inspect',base],capture_output=True).returncode:subprocess.run(['docker','tag',original['Image'],base],check=True)
folder=root/'tmp/document-upload-build';folder.mkdir(exist_ok=True)
files=['api.py','document_uploads.py','document_extract_stream.py','platform_api.py','platform_contracts.py','platform_documents.py','platform_knowledge.py','platform_runs.py','xlsx_documents.py']
dockerfile='FROM '+base+'\nCOPY web /app/web\n'
shutil.copytree(root/'moara/web/dist/moara-web/browser',folder/'web',dirs_exist_ok=True)
for name in files:
 shutil.copyfile(root/'moara/gateway'/name,folder/name);dockerfile+='COPY '+name+' /app/moara/gateway/'+name+'\n'
for name in ['migrations/011_streamed_documents.sql','alembic/versions/0011_streamed_documents.py']:
 shutil.copyfile(root/'moara/gateway'/name,folder/pathlib.Path(name).name);dockerfile+='COPY '+pathlib.Path(name).name+' /app/moara/gateway/'+name+'\n'
(folder/'Dockerfile').write_text(dockerfile)
subprocess.run(['docker','build','--network','none','-t',tag,str(folder)],check=True)
tests=folder/'tests';shutil.copytree(root/'tmp/legal-draft-build/tests',tests,dirs_exist_ok=True);shutil.copyfile(root/'moara/tests/test_document_uploads.py',tests/'test_document_uploads.py')
r=subprocess.run(['docker','run','--rm','--network','none','--read-only','--tmpfs','/tmp:size=160m','--memory','1g','--cap-drop','ALL','-v',str(tests)+':/tests:ro','--entrypoint','python',tag,'-m','unittest','discover','-s','/tests','-v'],text=True,capture_output=True)
print(r.stdout+r.stderr,flush=True)
image=subprocess.check_output(['docker','image','inspect',tag,'--format','{{.Id}}'],text=True).strip();match=re.search(r'Ran (\d+) tests',r.stdout+r.stderr)
(root/'tmp/document-upload-tests.json').write_text(json.dumps({'passed':r.returncode==0,'tests':int(match[1]) if match else None,'image':image}));r.check_returncode()
source=(root/'infrastructure/site-entry/build_chat_background.py').read_text();source=source[source.index('image=subprocess.check_output'):].replace('chat-background','document-upload').replace("'frontend_only':True","'frontend_only':False")
exec(compile(source,'document_upload_stage','exec'),globals())
(root/'tmp/unified-core-name.txt').write_text(name)
# The original /moara request policy remains the fallback. Only the
# authenticated streaming upload endpoint gets a body-size exemption.
text=(root/'infrastructure/caddy/Caddyfile').read_text()
start=text.index('  handle /moara/* {');opening=text.index('{',start);depth=1;end=opening+1
while depth:
 if text[end]=='{':depth+=1
 if text[end]=='}':depth-=1
 end+=1
body=text[opening+1:end-1]
replacement='''  @moara_document_upload {
    method POST
    path /moara/api/v1/platform/documents/upload /moara/api/v1/platform/documents/upload/
  }
  handle /moara/* {
    route {
      handle @moara_document_upload {
        reverse_proxy moara-gateway:8075 {
          flush_interval -1
        }
      }
      handle {'''+body+'''
      }
    }
  }'''
(root/'infrastructure/uploads/Caddyfile-candidate').write_text(text[:start]+replacement+text[end:])
(root/'tmp/document-upload-caddy-before').write_bytes((root/'infrastructure/caddy/Caddyfile').read_bytes())
