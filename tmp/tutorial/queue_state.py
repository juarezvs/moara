import subprocess
q="SELECT kind,status,count(*),max(round(extract(epoch from now()-updated_at))) FROM moara.platform_runs GROUP BY kind,status ORDER BY kind,status"
print(subprocess.check_output(['docker','exec','ai-server-postgres-1','psql','-U','postgres','-d','ai','-Atc',q],text=True))
code="import inspect;from moara.gateway.platform_schedules import tick;from moara.gateway.platform_runs import dispatch;print(inspect.getsource(dispatch))"
print(subprocess.check_output(['docker','exec','ai-server-moara-gateway-1','python','-c',code],text=True))
