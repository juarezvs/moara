import subprocess,json,hashlib
obj=json.loads(subprocess.check_output(['docker','inspect','ai-server-moara-gateway-1']))[0]
print(json.dumps({'command':obj['Config']['Cmd'],'entrypoint':obj['Config']['Entrypoint'],'code_mounts':[{'source':m['Source'],'destination':m['Destination']} for m in obj['Mounts'] if m['Destination'].startswith('/app')]}))
code="import inspect,json;from moara.gateway import api,platform_runs;print(json.dumps({'api_path':api.__file__,'dispatch_enabled':'create_task(platform_runs.dispatch(app))' in inspect.getsource(api)}))"
print(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',code],text=True))
