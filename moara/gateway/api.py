import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI,Depends,HTTPException,Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse,FileResponse,RedirectResponse,Response
from prometheus_client import CollectorRegistry,Counter,Histogram,generate_latest,CONTENT_TYPE_LATEST
from opentelemetry import trace
from opentelemetry.propagate import extract

from . import platform_api,platform_runs,platform_development
from .settings import Settings
from .database import Database
from .auth import Auth,require
from . import auth_api,identity_api,bootstrap,catalog_api,chat_api,admin_api,history_api,jobs_api,connectors_api,connector_tickets,observability

log=logging.getLogger('moara')
logging.basicConfig(level=logging.WARNING,format='%(message)s')
log.setLevel(logging.INFO)

def create_app(settings=None):
    config=settings or Settings.load()
    registry=CollectorRegistry()
    calls=Counter('moara_http_requests_total','HTTP requests',['route','status'],registry=registry)
    headers=Histogram('moara_http_headers_seconds','Time until response headers; streaming duration is recorded separately',['route'],registry=registry)
    operational=observability.OperationalMetrics(registry)

    @asynccontextmanager
    async def lifespan(app):
        app.state.settings=config;app.state.db=Database(config)
        app.state.registry=registry;app.state.operational=operational
        tracer=observability.tracing(config.version)
        app.state.http=httpx.AsyncClient(timeout=httpx.Timeout(30,connect=5),trust_env=False,follow_redirects=False,
            limits=httpx.Limits(max_connections=50,max_keepalive_connections=20))
        app.state.auth=Auth(config,app.state.db,app.state.http)
        app.state.identity=identity_api.IdentityStore(app.state.db)
        await app.state.auth.seed_roles();await app.state.identity.initialize()
        await bootstrap.seed(app.state.db,app.state.auth)
        dispatcher=asyncio.create_task(jobs_api.dispatch(app))
        platform_dispatcher=asyncio.create_task(platform_runs.dispatch(app))
        try:yield
        finally:
            dispatcher.cancel();platform_dispatcher.cancel()
            await asyncio.gather(dispatcher,platform_dispatcher,return_exceptions=True)
            await app.state.auth.close();await app.state.http.aclose();await app.state.db.dispose()
            if tracer:await asyncio.to_thread(tracer.shutdown)

    app=FastAPI(title='Moara AI Gateway',version=config.version,lifespan=lifespan,
        docs_url=None,redoc_url=None,openapi_url=None,root_path='/moara')

    @app.middleware('http')
    async def security(request:Request,call_next):
        identifier=request.headers.get('x-request-id','')
        try:identifier=uuid.UUID(identifier)
        except (ValueError,TypeError):identifier=uuid.uuid4()
        request.state.request_id=identifier
        started=time.monotonic();body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>8*1024**2:return JSONResponse({'detail':'request_too_large','request_id':str(identifier)},413)
        request._body=bytes(body)
        with trace.get_tracer('moara.gateway').start_as_current_span('http.request',context=extract(request.headers)) as span:
            span.set_attribute('moara.request_id',str(identifier));span.set_attribute('http.request.method',request.method)
            try:response=await call_next(request)
            except Exception as error:
                # Never log parameters, prompts, SQL rows, credentials or exception messages.
                log.error(json.dumps({'event':'request_error','request_id':str(identifier),'error_type':type(error).__name__}))
                response=JSONResponse({'detail':'internal_error','request_id':str(identifier)},500)
            route=getattr(request.scope.get('route'),'path','unmatched')
            span.set_attribute('http.route',route);span.set_attribute('http.response.status_code',response.status_code)
            context=span.get_span_context();trace_id=f'{context.trace_id:032x}' if context.is_valid else None
        duration=time.monotonic()-started
        calls.labels(route,str(response.status_code)).inc();headers.labels(route).observe(duration)
        log.info(json.dumps({'event':'request','request_id':str(identifier),'method':request.method,'route':route,
            'status':response.status_code,'headers_ms':round(duration*1000),'trace_id':trace_id}))
        if trace_id:response.headers['X-Trace-ID']=trace_id
        response.headers.update({'X-Request-ID':str(identifier),'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
            'X-Frame-Options':'DENY','Cache-Control':'no-store','Permissions-Policy':'camera=(),microphone=(),geolocation=()',
            'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'"})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation(request,error):
        return JSONResponse({'detail':'invalid_request','fields':['.'.join(map(str,e['loc'])) for e in error.errors()[:12]],
            'request_id':str(request.state.request_id)},422)

    @app.get('/api/v1/health',tags=['Operations'])
    async def health():return {'status':'ok','service':'moara-gateway','version':config.version}

    @app.get('/api/v1/ready',tags=['Operations'])
    async def ready(request:Request):
        try:
            await request.app.state.db.execute('SELECT 1 AS ok',one=True)
            await request.app.state.auth.redis.ping()
            await request.app.state.identity.active()
        except Exception:return JSONResponse({'status':'not_ready'},503)
        return {'status':'ready','database':True,'redis':True,'institutional_identity':True}

    @app.get('/api/v1/metrics',tags=['Operations'])
    async def metrics(actor=Depends(require('status.read'))):return Response(generate_latest(registry),media_type=CONTENT_TYPE_LATEST)

    @app.get('/api/v1/openapi.json',tags=['Operations'])
    async def openapi(actor=Depends(require('status.read'))):
        data=app.openapi();data['servers']=[{'url':'/moara'}];return data

    @app.get('/api/v1/audit',tags=['Audit'])
    async def audit(request:Request,limit:int=50,actor=Depends(require('audit.read'))):
        if not 1<=limit<=200:raise HTTPException(422,'invalid_limit')
        return await request.app.state.db.execute('SELECT * FROM moara.audit ORDER BY id DESC LIMIT :limit',{'limit':limit})

    app.include_router(auth_api.router);app.include_router(identity_api.router)
    app.include_router(catalog_api.router);app.include_router(chat_api.router)
    app.include_router(catalog_api.compat_router)
    app.include_router(admin_api.router)
    app.include_router(history_api.router)
    app.include_router(jobs_api.router)
    app.include_router(connectors_api.router)
    app.include_router(connector_tickets.router)
    app.include_router(observability.router)
    app.include_router(platform_api.router)
    app.include_router(platform_development.router)

    @app.get('/',include_in_schema=False)
    async def index():
        path=Path('/app/web/index.html')
        if not path.is_file():raise HTTPException(503,'moara_frontend_not_built')
        return FileResponse(path)

    @app.get('/{path:path}',include_in_schema=False)
    async def frontend(path:str):
        if path.startswith(('api/','v1/')):raise HTTPException(404,'endpoint_not_found')
        root=Path('/app/web');target=(root/path).resolve()
        if not target.is_relative_to(root):raise HTTPException(404)
        if target.is_file():return FileResponse(target)
        if '.' in Path(path).name:raise HTTPException(404)
        return await index()
    return app
