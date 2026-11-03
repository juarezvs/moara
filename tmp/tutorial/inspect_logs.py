import subprocess,json
s=subprocess.check_output(['docker','logs','--tail','600','ai-server-moara-gateway-1'],stderr=subprocess.STDOUT).decode(errors='replace')
for line in s.splitlines():
 if any(t in line for t in ['Task exception','ModuleNotFoundError','ImportError','NameError','AttributeError','platform_dispatch','platform_runs.py','platform_schedules.py']):print(line[:400])
