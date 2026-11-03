import pathlib,subprocess,importlib.util,json,ssl,urllib.request
root=pathlib.Path('/home/nutec/ai-server')
spec=importlib.util.spec_from_file_location('maintenance',root/'infrastructure/scripts/webui_maintenance.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
tls=ssl.create_default_context(cafile=str(root/'docs/runtime/moara-domain-root-ca.crt'))
token=m.admin_session();report={}
for endpoint in ['/api/models','/api/v1/retrieval/config']:
 try:
  request=urllib.request.Request('https://moara.am.trf1.gov.br'+endpoint,headers={'Authorization':'Bearer '+token})
  with urllib.request.urlopen(request,context=tls,timeout=30) as response:value=json.load(response)
  if endpoint.endswith('/models'):
   report['models']=[{'id':row.get('id'),'system_utf8_bytes':len(str(row.get('info',{}).get('params',{}).get('system','')).encode()),'params_keys':list(row.get('info',{}).get('params',{})),
     'max_tokens':row.get('info',{}).get('params',{}).get('max_tokens')} for row in value.get('data',[])]
  else:
   def filtered(obj,prefix=''):
    result={}
    for key,val in obj.items():
     if isinstance(val,dict):result.update(filtered(val,prefix+key+'.'))
     elif key.lower() in ['top_k','top_k_reranker','chunk_size','chunk_overlap','full_context','bypass_embedding_and_retrieval','rag_template','template']:
      result[prefix+key]=len(val.encode()) if isinstance(val,str) else val
    return result
   report['retrieval']=filtered(value)
 except Exception as error:report[endpoint]={'error_type':type(error).__name__}
print(json.dumps(report))
