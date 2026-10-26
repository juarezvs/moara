"""Production checks expose only booleans, versions and aggregate counters."""
import importlib.util
import json
import ssl
import subprocess
import time
import urllib.request
import urllib.error
import http.cookiejar
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
checks={}
def check(name,value):
    checks[name]=bool(value)
    if not value:raise AssertionError(name)

def main():
    spec=importlib.util.spec_from_file_location('maintenance',ROOT/'infrastructure/scripts/webui_maintenance.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    tls=ssl.create_default_context(cafile=str(ROOT/'docs/runtime/ai-root-ca.crt'))
    cookies=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=tls),urllib.request.HTTPCookieProcessor(cookies))
    origin='https://localhost:8443'
    def request(path,headers=None,body=None):
        r=urllib.request.Request(origin+path,headers=headers or {},data=json.dumps(body).encode() if body is not None else None)
        try:
            with opener.open(r,timeout=30) as value:return value.status,value.headers,value.read()
        except urllib.error.HTTPError as e:return e.code,e.headers,e.read()
    status,_,body=request('/moara/monitoramento/api/user',{'X-WEBAUTH-USER':'forged-admin','X-Moara-Metrics-User':'forged-admin'})
    check('forged_anonymous_identity_denied',status in (401,403) or b'<title>Moara AI</title>' in body)
    token=module.admin_session()
    status,_,body=request('/moara/api/v1/auth/session',{'Origin':origin,'Authorization':'Bearer '+token},{})
    check('real_session_created',status==200)
    csrf=json.loads(body)['csrf_token']
    status,headers,body=request('/moara/api/v1/observability/host')
    host=json.loads(body)
    check('fresh_real_host_metrics',status==200 and host['available'] and host['cpu_percent'] is not None and host['memory_total_bytes']>200*1024**3)
    trace=headers.get('X-Trace-ID')
    check('actual_trace_identifier',bool(trace) and len(trace)==32 and int(trace,16)>0)
    status,_,body=request('/moara/monitoramento/api/user')
    user=json.loads(body)
    check('grafana_authenticated_proxy',status==200 and user.get('login','').startswith('webui:'))
    check('grafana_is_not_server_admin',not user.get('isGrafanaAdmin',True))
    status,_,body=request('/moara/monitoramento/api/dashboards/uid/moara-operations')
    dashboard=json.loads(body)
    check('provisioned_real_dashboard',status==200 and len(dashboard['dashboard']['panels'])>=6)
    status,_,_=request('/moara/api/v1/observability/scrape')
    check('scrape_requires_separate_service_credential',status==401)
    code='''import json,urllib.request
value=json.load(urllib.request.urlopen('http://moara-prometheus:9090/api/v1/targets',timeout=5))
print(json.dumps({'up':all(t['health']=='up' for t in value['data']['activeTargets']),'count':len(value['data']['activeTargets'])}))
'''
    end=time.monotonic()+45
    while True:
        result=subprocess.run(['docker','exec','-i','ai-server-moara-gateway-1','python','-'],input=code,text=True,capture_output=True,check=True)
        targets=json.loads(result.stdout)
        if targets['up'] or time.monotonic()>end:break
        time.sleep(2)
    check('prometheus_real_scrape_up',targets['up'] and targets['count']>0)
    # Correlation proof: inspect metadata-only collector records without printing them.
    end=time.monotonic()+20
    while True:
        logs=subprocess.run(['docker','logs','--since','60s','ai-server-moara-otel-1'],capture_output=True,text=True)
        found=trace in logs.stdout+logs.stderr
        if found or time.monotonic()>end:break
        time.sleep(2)
    check('trace_exported_to_local_collector',found)
    for service in ['moara-prometheus','moara-grafana','moara-otel']:
        obj=json.loads(subprocess.check_output(['docker','inspect','ai-server-'+service+'-1']))[0]
        check(service+'_no_published_ports',not obj['HostConfig']['PortBindings'])
        check(service+'_isolated_network',set(obj['NetworkSettings']['Networks'])=={'ai-server_moara_telemetry'})
    return {'passed':True,'checks':checks,'scope':'real HTTPS/session/Grafana/Prometheus/OTLP; aggregate host metrics only'}

if __name__=='__main__':
    try:report=main()
    except Exception as error:report={'passed':False,'checks':checks,'failure_type':type(error).__name__}
    (ROOT/'docs/runtime/moara-observability-acceptance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report));raise SystemExit(0 if report['passed'] else 1)
