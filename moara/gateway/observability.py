"""Metadata-only operational metrics and OpenTelemetry spans."""
import hmac
import json
import os
import time
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException,Request
from fastapi.responses import Response,RedirectResponse
from prometheus_client import Gauge,generate_latest,CONTENT_TYPE_LATEST
from .auth import current_actor,require
router=APIRouter(tags=['Observability'])

def host_snapshot():
    try:
        path=Path('/run/moara/host.json')
        if path.stat().st_size>256000:raise ValueError()
        value=json.loads(path.read_text());age=time.time()-value['observed_at']
        if value.get('version')!=1 or not 0<=age<=45:return {'available':False,'reason':'stale','age_seconds':round(age)}
        return {'available':True,'age_seconds':round(age),**value}
    except Exception:return {'available':False,'reason':'collector_unavailable'}

def tracing(version):
    endpoint=os.getenv('OTEL_EXPORTER_OTLP_TRACES_ENDPOINT')
    if not endpoint:return None
    # This exporter is explicitly local. No request bodies or authentication headers
    # are instrumented, and no automatic instrumentation package is installed.
    if endpoint!='http://moara-otel:4318/v1/traces':raise RuntimeError('Only the local telemetry collector is permitted')
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    provider=TracerProvider(resource=Resource.create({'service.name':'moara-gateway','service.version':version,'deployment.environment.name':'local'}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint,timeout=2),max_queue_size=2048,max_export_batch_size=128,schedule_delay_millis=5000))
    trace.set_tracer_provider(provider);return provider

class OperationalMetrics:
    def __init__(self,registry):
        self.fresh=Gauge('moara_host_metrics_fresh','Host collector produced a recent real measurement',registry=registry)
        self.cpu_ready=Gauge('moara_host_cpu_measurement_ready','At least two host CPU counter observations exist',registry=registry)
        self.cpu=Gauge('moara_host_cpu_percent','Host busy CPU percent from proc counters',registry=registry)
        self.memory=Gauge('moara_host_memory_used_bytes','Host used RAM, total minus available',registry=registry)
        self.total=Gauge('moara_host_memory_total_bytes','Host total RAM',registry=registry)
        self.disk=Gauge('moara_host_disk_free_bytes','Free space on the deployment filesystem',registry=registry)
        self.container_cpu=Gauge('moara_container_cpu_percent','Actual Docker CPU percent; may exceed 100 for multiple logical CPUs',['container'],registry=registry)
        self.container_memory=Gauge('moara_container_memory_bytes','Actual Docker memory working set',['container'],registry=registry)
        self.jobs=Gauge('moara_jobs','Durable job count by state',['state'],registry=registry)
    async def collect(self,app):
        host=host_snapshot();self.fresh.set(int(host['available']))
        if host['available']:
            self.cpu_ready.set(int(host.get('cpu_percent') is not None))
            if host.get('cpu_percent') is not None:self.cpu.set(host['cpu_percent'])
            self.memory.set(host['memory_total_bytes']-host['memory_available_bytes']);self.total.set(host['memory_total_bytes']);self.disk.set(host['disk_free_bytes'])
            self.container_cpu.clear();self.container_memory.clear()
            for container in host.get('containers',[]):
                name=container.get('name','')
                if not name.startswith('ai-server-') or len(name)>100:continue
                self.container_cpu.labels(name).set(container['cpu_percent'])
                if container['memory_bytes'] is not None:self.container_memory.labels(name).set(container['memory_bytes'])
        self.jobs.clear()
        for row in await app.state.db.execute('SELECT status,count(*) AS total FROM moara.jobs GROUP BY status'):
            self.jobs.labels(row['status']).set(row['total'])

@router.get('/api/v1/observability/authorize',include_in_schema=False)
async def authorize(request:Request):
    try:actor=await current_actor(request);actor.require('status.read')
    except HTTPException as error:
        if error.status_code==401:return RedirectResponse('/moara/login',303)
        raise
    if actor.key_id or actor.auth_source=='integration':raise HTTPException(403,'interactive_session_required')
    return Response(status_code=204,headers={'X-Moara-Metrics-User':actor.subject,'X-Moara-Metrics-Role':'Viewer'})

@router.get('/api/v1/observability/host')
async def host(actor=Depends(require('status.read'))):return host_snapshot()

@router.get('/api/v1/observability/scrape',include_in_schema=False)
async def scrape(request:Request):
    key=request.app.state.settings.metrics_key
    if not key or not hmac.compare_digest(request.headers.get('authorization',''),'Bearer '+key):raise HTTPException(401,'metrics_service_required')
    await request.app.state.operational.collect(request.app)
    return Response(generate_latest(request.app.state.registry),media_type=CONTENT_TYPE_LATEST)
