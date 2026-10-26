import asyncio
import json
import mimetypes
import os
import re
import shutil
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

import browser
import core
import jobs
import vision

async def retention_loop():
    while True:
        setting = await core.sql("SELECT value FROM studio_settings WHERE name='retention_days'", one=True)
        days = int(setting['value']) if setting else 7
        expired = await core.sql("SELECT id FROM studio_jobs WHERE status NOT IN ('queued','running') AND updated_at < now() - (%s * interval '1 day')", (days,))
        for row in expired:
            path = core.DATA / str(row['id'])
            if path.is_dir():
                shutil.rmtree(path)
            await core.sql('DELETE FROM studio_jobs WHERE id=%s', (row['id'],))
        await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app):
    core.HTTP = httpx.AsyncClient(timeout=httpx.Timeout(30, connect=10), trust_env=False)
    await core.initialize()
    demo = await core.sql("SELECT id FROM studio_systems WHERE name='Demonstração IA Studio'", one=True)
    if not demo:
        settings = core.authorized_settings('http://studio-demo:8092/', [], ['/'], ['[data-private]'], ['#periodo'], 'demo')
        settings['shared_demo'] = True
        await core.sql('INSERT INTO studio_systems(id,owner,name,settings) VALUES (%s,%s,%s,%s)',
            (str(uuid.uuid4()), 'system', 'Demonstração IA Studio', Jsonb(settings)))
    app.state.worker = asyncio.create_task(jobs.worker())
    app.state.retention = asyncio.create_task(retention_loop())
    yield
    for task in list(jobs.ACTIVE.values()):
        task.cancel()
    if jobs.ACTIVE:
        await asyncio.gather(*list(jobs.ACTIVE.values()), return_exceptions=True)
    app.state.worker.cancel()
    app.state.retention.cancel()
    await asyncio.gather(app.state.worker, app.state.retention, return_exceptions=True)
    await core.HTTP.aclose()

app = FastAPI(title='Moara Studio — Plataforma Local de Inteligência Artificial Generativa', version='1.0.0',
    lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None, root_path='/studio')

@app.middleware('http')
async def limits(request: Request, call_next):
    content = bytearray()
    async for chunk in request.stream():
        content.extend(chunk)
        if len(content) > 8 * 1024**2:
            return JSONResponse({'detail': 'Arquivo ou solicitação excede 8 MB'}, status_code=413)
    request._body = bytes(content)
    try:
        response = await call_next(request)
    except Exception as exc:
        # Do not echo model output, credentials, browser fields or SQL parameters.
        return JSONResponse({'detail': 'Falha interna controlada', 'error_type': type(exc).__name__}, status_code=500)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    return JSONResponse({'detail': 'Confira os parâmetros informados',
        'fields': ['.'.join(map(str, e['loc'])) for e in exc.errors()[:10]]}, status_code=422)

@app.get('/health')
async def health():
    await core.sql('SELECT 1')
    return {'ok': not app.state.worker.done(), 'queue': 'postgresql', 'local_only': True}

class Login(BaseModel):
    email: str = Field(max_length=160)
    password: str = Field(max_length=256)

@app.post('/api/auth/login')
async def login(body: Login):
    response = await core.HTTP.post('http://webui:8080/api/v1/auths/signin', json=body.model_dump())
    if response.status_code != 200:
        raise HTTPException(401, 'Usuário ou senha inválidos')
    user = response.json()
    if user.get('role') not in ('admin', 'user'):
        raise HTTPException(403, 'Conta pendente de autorização')
    result = JSONResponse({'name': user['name'], 'role': user['role']})
    result.set_cookie('studio_token', user['token'], secure=True, httponly=True, samesite='strict', path='/studio', max_age=86400)
    return result

@app.post('/auth/login', include_in_schema=False)
async def form_login(request: Request):
    # Safe fallback when the application script has not loaded. Never use GET for credentials.
    raw = await request.body()
    if len(raw) > 4096 or request.headers.get('content-type', '').split(';')[0] != 'application/x-www-form-urlencoded':
        raise HTTPException(422, 'Formulário inválido')
    try:
        values = parse_qs(raw.decode('utf-8'), max_num_fields=4)
        body = Login(email=values.get('email', [''])[0].strip(), password=values.get('password', [''])[0])
        result = await login(body)
    except (ValueError, HTTPException):
        page = (Path(__file__).parent / 'static/index.html').read_text(encoding='utf-8')
        page = page.replace('id="login-error" role="alert">', 'id="login-error" role="alert">Não foi possível entrar. Confira o e-mail e a senha da sua conta no Moara AI.')
        return HTMLResponse(page, status_code=401)
    redirect = RedirectResponse('/studio/', status_code=303)
    redirect.headers['set-cookie'] = result.headers['set-cookie']
    return redirect

@app.post('/api/auth/logout')
async def logout(user=Depends(core.actor)):
    response = JSONResponse({'ok': True})
    response.delete_cookie('studio_token', path='/studio')
    return response

@app.post('/api/auth/session')
async def reuse_chat_session(request: Request, user=Depends(core.actor)):
    authorization = request.headers.get('authorization', '')
    token = authorization[7:] if authorization.startswith('Bearer ') else ''
    if not token or token.count('.') != 2 or not user.owner.startswith('webui:'):
        raise HTTPException(401, 'Abra o Moara AI e entre com sua conta.')
    # actor verified the token with WebUI; the client cannot choose identity or role.
    result = JSONResponse({'name': user.name, 'role': 'admin' if user.admin else 'user'})
    result.set_cookie('studio_token', token, secure=True, httponly=True, samesite='strict', path='/studio', max_age=86400)
    return result

@app.get('/api/auth/me')
async def me(user=Depends(core.actor)):
    return {'owner': user.owner, 'name': user.name, 'admin': user.admin, 'permissions': sorted(user.scopes)}

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Design(Strict):
    prompt: str = Field(min_length=8, max_length=5000)
    application: Literal['Dashboard', 'Landing page', 'Formulário', 'Componente'] = 'Dashboard'
    framework: Literal['html', 'react', 'angular'] = 'html'
    style: Literal['cloud', 'minimal', 'institutional'] = 'cloud'
    color: str = Field(default='#2563eb', pattern=r'^#[0-9a-fA-F]{6}$')
    brand: str = Field(default='Moara AI', max_length=40)
    theme: Literal['light', 'dark'] = 'light'
    width: int = Field(default=1440, ge=320, le=1920)
    height: int = Field(default=1000, ge=480, le=1600)
    model: Literal['general', 'coding'] = 'general'
    components: list[str] = Field(default_factory=list, max_length=12)
    reference: str | None = Field(default=None, max_length=2800000)
    parent_job: str | None = None

class ImageRequest(Strict):
    prompt: str = Field(min_length=5, max_length=2000)
    profile: Literal['economic', 'balanced', 'quality'] = 'balanced'
    size: Literal['384x384', '512x512'] | None = None
    steps: int | None = Field(default=None, ge=1, le=4)
    seed: int = Field(default=-1, ge=-1, le=2147483647)

class Explore(Strict):
    system_id: str = Field(default='demo', max_length=64)
    prompt: str = Field(default='Explore as páginas autorizadas somente em leitura', max_length=3000)
    max_pages: int = Field(default=6, ge=1, le=12)
    depth: int = Field(default=2, ge=0, le=3)

class Manual(Explore):
    title: str = Field(default='Manual de utilização', max_length=120)
    audience: str = Field(default='Usuários autorizados', max_length=100)
    source_job: str | None = None
    review_note: str = Field(default='', max_length=4000)
    section_reviews: dict[str, str] = Field(default_factory=dict, max_length=12)

class Vision(Strict):
    prompt: str = Field(default='Descreva os componentes e sugira melhorias nesta interface.', max_length=4000)
    images: list[str] = Field(min_length=1, max_length=2)

class Chat(Strict):
    prompt: str = Field(min_length=1, max_length=5000)
    model: Literal['general', 'coding', 'qwen25-coder-32b', 'llama31-70b', 'llama33-70b', 'deepseek-coder-v2-lite'] = 'general'
    system_id: str | None = None

@app.post('/api/design/generate', tags=['Design'])
async def design_generate(body: Design, user=Depends(core.actor)):
    if body.reference:
        core.require(user, 'vision')
        vision.preprocess(body.reference)
    return await jobs.submit('design', body.model_dump(), user)

@app.post('/api/design/{job_id}/refine', tags=['Design'])
async def refine(job_id: str, body: Design, user=Depends(core.actor)):
    previous = await core.owned_job(job_id, user)
    if previous['kind'] != 'design':
        raise HTTPException(422, 'Escolha um projeto de design')
    data = {**previous['input'], **body.model_dump(exclude_unset=True), 'parent_job': job_id}
    data['prompt'] = 'Projeto anterior: ' + previous['input']['prompt'] + '\nRefinamento solicitado: ' + body.prompt
    return await jobs.submit('design', data, user)

@app.post('/api/images/generate', tags=['Images'])
async def images_generate(body: ImageRequest, user=Depends(core.actor)):
    return await jobs.submit('images', body.model_dump(), user)

@app.get('/api/images/models', tags=['Images'])
async def image_models(user=Depends(core.actor)):
    core.require(user, 'images')
    response = await core.HTTP.get('http://gateway:8000/v1/images/models', headers={'Authorization': 'Bearer ' + core.SERVICE_KEY})
    if response.status_code != 200:
        raise HTTPException(503, 'Motor de imagens indisponível')
    return {**response.json(), 'profiles': jobs.PROFILES}

@app.post('/api/vision/analyze', tags=['Vision'])
@app.post('/api/vision/compare', tags=['Vision'])
async def vision_analyze(body: Vision, user=Depends(core.actor)):
    for image in body.images:
        try:
            vision.preprocess(image)
        except Exception:
            raise HTTPException(422, 'Imagem inválida; use PNG, JPEG ou WebP de até 2 MB') from None
    return await jobs.submit('vision', body.model_dump(), user)

@app.get('/api/vision/models', tags=['Vision'])
async def vision_models(user=Depends(core.actor)):
    core.require(user, 'vision')
    response = await core.HTTP.get('http://gateway:8000/v1/vision/models', headers={'Authorization': 'Bearer ' + core.SERVICE_KEY})
    return response.json() if response.status_code == 200 else {'models': [], 'available': False}

@app.post('/api/browser/explore', tags=['Browser'])
async def explore(body: Explore, user=Depends(core.actor)):
    return await jobs.submit('browser', body.model_dump(), user)

@app.post('/api/manuals/generate', tags=['Manuals'])
async def manual_generate(body: Manual, user=Depends(core.actor)):
    return await jobs.submit('manuals', body.model_dump(), user)

@app.post('/api/chat', tags=['Orchestrator'])
async def chat(body: Chat, user=Depends(core.actor)):
    core.require(user, 'chat')
    kind = await jobs.classify(body.prompt, body.system_id)
    if kind == 'vision':
        return {'needs_input': 'Anexe a imagem na área Analisar imagens.', 'kind': kind}
    if kind in ('browser', 'manuals') and not body.system_id:
        return {'needs_input': 'Selecione um sistema autorizado para essa tarefa.', 'kind': kind}
    if kind == 'design':
        return await design_generate(Design(prompt=body.prompt), user)
    if kind == 'images':
        return await images_generate(ImageRequest(prompt=body.prompt), user)
    if kind == 'browser':
        return await explore(Explore(prompt=body.prompt, system_id=body.system_id), user)
    if kind == 'manuals':
        return await manual_generate(Manual(prompt=body.prompt, system_id=body.system_id), user)
    return await jobs.submit('chat', body.model_dump(), user)

@app.get('/api/chat/models', tags=['Orchestrator'])
async def chat_models(user=Depends(core.actor)):
    core.require(user, 'chat')
    response = await core.HTTP.get('http://gateway:8000/v1/models', headers={'Authorization': 'Bearer ' + core.SERVICE_KEY})
    if response.status_code != 200:
        raise HTTPException(503, 'Catálogo de modelos indisponível')
    return response.json()

@app.get('/api/jobs', tags=['Jobs'])
async def list_jobs(user=Depends(core.actor)):
    return await core.sql('SELECT id,kind,status,progress,stage,created_at,updated_at,cancel_requested FROM studio_jobs WHERE owner=%s ORDER BY created_at DESC LIMIT 100', (user.owner,))

@app.get('/api/jobs/{job_id}', tags=['Jobs'])
@app.get('/api/images/{job_id}', tags=['Images'])
@app.get('/api/browser/jobs/{job_id}', tags=['Browser'])
@app.get('/api/manuals/{job_id}', tags=['Manuals'])
async def get_job(job_id: str, user=Depends(core.actor)):
    job = await core.owned_job(job_id, user)
    # Input uploads and private credentials are not returned by status polling.
    return {k: v for k, v in job.items() if k != 'input'}

@app.post('/api/jobs/{job_id}/cancel', tags=['Jobs'])
@app.post('/api/images/{job_id}/cancel', tags=['Images'])
@app.post('/api/browser/jobs/{job_id}/cancel', tags=['Browser'])
@app.post('/api/manuals/{job_id}/cancel', tags=['Manuals'])
async def cancel_job(job_id: str, user=Depends(core.actor)):
    return await jobs.cancel(await core.owned_job(job_id, user), user)

@app.get('/api/jobs/{job_id}/events', tags=['Jobs'])
async def events(job_id: str, user=Depends(core.actor)):
    await core.owned_job(job_id, user)
    async def stream():
        last = 0
        for _ in range(1200):
            rows = await core.sql('SELECT id,stage,progress,created_at FROM studio_events WHERE job_id=%s AND owner=%s AND id>%s ORDER BY id', (job_id, user.owner, last))
            for row in rows:
                last = row['id']
                yield 'data: ' + json.dumps(jsonable_encoder(row), ensure_ascii=False) + '\n\n'
            state = await core.sql('SELECT status FROM studio_jobs WHERE id=%s AND owner=%s', (job_id, user.owner), one=True)
            if state['status'] not in ('queued', 'running'):
                yield 'event: done\ndata: ' + json.dumps(state) + '\n\n'
                return
            if not rows:
                yield ': keepalive\n\n'
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'X-Accel-Buffering': 'no'})

@app.get('/api/jobs/{job_id}/logs', tags=['Jobs'])
async def logs(job_id: str, user=Depends(core.actor)):
    await core.owned_job(job_id, user)
    return await core.sql('SELECT stage,progress,created_at FROM studio_events WHERE job_id=%s AND owner=%s ORDER BY id', (job_id, user.owner))

@app.get('/api/jobs/{job_id}/files/{filename}', tags=['Artifacts'])
async def artifact(job_id: str, filename: str, download: bool = False, user=Depends(core.actor)):
    job = await core.owned_job(job_id, user)
    if job['status'] != 'completed' or filename not in job['result'].get('artifacts', []):
        raise HTTPException(404, 'Artefato não disponível')
    path = core.file_path(job_id, filename)
    media = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
    headers = {'Content-Security-Policy': "default-src 'none'; style-src 'unsafe-inline'; img-src data:; frame-ancestors 'self'; sandbox"} if filename.endswith('.html') else {}
    return FileResponse(path, media_type=media, filename=filename if download else None, headers=headers)

@app.get('/api/images/{job_id}/download', tags=['Images'])
async def download_image(job_id: str, user=Depends(core.actor)):
    return await artifact(job_id, 'image.png', True, user)

@app.get('/api/manuals/{job_id}/download', tags=['Manuals'])
async def download_manual(job_id: str, user=Depends(core.actor)):
    return await artifact(job_id, 'manual.pdf', True, user)

@app.get('/api/manuals/{job_id}/preview', tags=['Manuals'])
async def preview_manual(job_id: str, user=Depends(core.actor)):
    return await artifact(job_id, 'manual.html', False, user)

@app.get('/api/browser/jobs/{job_id}/evidence', tags=['Browser'])
async def browser_evidence(job_id: str, user=Depends(core.actor)):
    job = await core.owned_job(job_id, user)
    return job['result'].get('metadata', {})

class SystemRegistration(Strict):
    name: str = Field(min_length=3, max_length=100)
    base_url: str = Field(max_length=1000)
    environment: Literal['demo', 'development', 'staging'] = 'staging'
    origins: list[str] = Field(default_factory=list, max_length=8)
    paths: list[str] = Field(default_factory=lambda: ['/'], max_length=20)
    masks: list[str] = Field(default_factory=list, max_length=20)
    allowed_fill: list[str] = Field(default_factory=list, max_length=20)
    allowed_owners: list[str] = Field(default_factory=list, max_length=50)
    login: dict | None = None

@app.post('/api/systems', tags=['Administration'])
async def register_system(body: SystemRegistration, user=Depends(core.actor)):
    if not user.admin:
        raise HTTPException(403, 'Somente administradores cadastram destinos')
    resolved = await core.renderer('/resolve', {'urls': [body.base_url, *body.origins]})
    settings = core.authorized_settings(body.base_url, body.origins, body.paths, body.masks, body.allowed_fill, body.environment, resolved['hosts'])
    settings['allowed_owners'] = body.allowed_owners
    encrypted = None
    if body.login:
        needed = {'url', 'username_selector', 'password_selector', 'submit_selector', 'username', 'password'}
        if set(body.login) != needed or len(json.dumps(body.login)) > 8000:
            raise HTTPException(422, 'Perfil de login inválido')
        from urllib.parse import urlsplit
        p = urlsplit(body.login['url'])
        if p.scheme + '://' + p.netloc not in settings['origins']:
            raise HTTPException(403, 'Login fora dos destinos autorizados')
        encrypted = core.CRYPTO.encrypt(json.dumps(body.login).encode())
    identifier = str(uuid.uuid4())
    await core.sql('INSERT INTO studio_systems(id,owner,name,settings,credentials) VALUES (%s,%s,%s,%s,%s)',
        (identifier, user.owner, body.name, Jsonb(settings), encrypted))
    await core.audit(user, 'system.register', identifier)
    return {'id': identifier, 'name': body.name}

@app.get('/api/systems', tags=['Browser'])
async def systems(user=Depends(core.actor)):
    rows = await core.sql('SELECT id,owner,name,settings FROM studio_systems ORDER BY name')
    return [{'id': row['id'], 'name': row['name'], 'base_url': row['settings']['base_url'],
        'environment': row['settings']['environment']} for row in rows if user.admin or row['owner'] == user.owner
        or row['settings'].get('shared_demo') or user.owner in row['settings'].get('allowed_owners', [])]

class Session(Strict):
    system_id: str = 'demo'
    mode: Literal['observe'] = 'observe'

@app.post('/api/browser/sessions', tags=['Browser'])
async def create_session(body: Session, user=Depends(core.actor)):
    core.require(user, 'browser')
    system = await browser.get_system(body.system_id, user.owner, user.admin)
    result = await browser.create_session(system, user.owner)
    await core.audit(user, 'browser.session.start', result['session_id'])
    return result

@app.get('/api/browser/sessions/{sid}', tags=['Browser'])
async def get_session(sid: str, user=Depends(core.actor)):
    core.require(user, 'browser')
    await browser.owned_session(sid, user.owner)
    return await core.renderer('/sessions/' + sid + '/snapshot', method='GET')

class Action(Strict):
    action: Literal['goto', 'click', 'fill', 'select', 'scroll', 'back', 'snapshot']
    target: str = Field(default='', max_length=1000)
    value: str = Field(default='', max_length=500)

@app.post('/api/browser/sessions/{sid}/actions', tags=['Browser'])
async def session_action(sid: str, body: Action, user=Depends(core.actor)):
    core.require(user, 'browser')
    await browser.owned_session(sid, user.owner)
    result = await core.renderer('/sessions/' + sid + '/actions', body.model_dump())
    # Values filled into fields and credential data are never recorded in the audit trail.
    await browser.record(sid, user.owner, dict(result), 'Ação compartilhada: ' + body.action)
    await core.audit(user, 'browser.action.' + body.action, sid)
    return result

@app.delete('/api/browser/sessions/{sid}', tags=['Browser'])
async def close_session(sid: str, user=Depends(core.actor)):
    await browser.owned_session(sid, user.owner)
    await core.renderer('/sessions/' + sid, method='DELETE')
    await core.sql("UPDATE studio_sessions SET status='closed' WHERE id=%s", (sid,))
    return {'closed': True}

@app.get('/api/status', tags=['Administration'])
async def status(user=Depends(core.actor)):
    services = {}
    for name, url in [('gateway', 'http://gateway:8000/health'), ('browser', 'http://studio-renderer:8091/health')]:
        try:
            response = await core.HTTP.get(url, timeout=10)
            services[name] = {'ok': response.status_code == 200, 'details': response.json()}
        except httpx.HTTPError:
            services[name] = {'ok': False}
    memory = dict((line.split(':')[0], int(line.split()[1])) for line in Path('/proc/meminfo').read_text().splitlines())
    queue = await core.sql('SELECT status,count(*) AS count FROM studio_jobs GROUP BY status')
    return {'services': services, 'memory_gib': round(memory['MemTotal'] / 1024**2, 1),
        'available_gib': round(memory['MemAvailable'] / 1024**2, 1),
        'load': Path('/proc/loadavg').read_text().split()[:3], 'cpu_threads': os.cpu_count(),
        'jobs': queue, 'studio_concurrency': 1, 'profiles': jobs.PROFILES,
        'models': {'general': 'Gemma 4 local', 'coding': 'Qwen3-Coder local', 'images': 'SD-Turbo CPU', 'vision': 'Gemma 4 · capacidade verificada'}}

@app.get('/api/admin/audit', tags=['Administration'])
async def audit_log(user=Depends(core.actor)):
    if not user.admin:
        raise HTTPException(403, 'Somente administradores')
    return await core.sql('SELECT owner,action,resource,created_at FROM studio_audit ORDER BY id DESC LIMIT 200')

class PermissionUpdate(Strict):
    owner: str = Field(pattern=r'^webui:[a-zA-Z0-9_-]{1,80}$')
    scopes: list[Literal['chat', 'design', 'images', 'vision', 'browser', 'manuals']]

@app.put('/api/admin/permissions', tags=['Administration'])
async def permissions(body: PermissionUpdate, user=Depends(core.actor)):
    if not user.admin:
        raise HTTPException(403, 'Somente administradores')
    await core.sql('INSERT INTO studio_permissions(owner,scopes) VALUES (%s,%s) ON CONFLICT(owner) DO UPDATE SET scopes=excluded.scopes',
        (body.owner, Jsonb(sorted(set(body.scopes)))))
    await core.audit(user, 'permissions.update', body.owner)
    return body.model_dump()

class Retention(Strict):
    days: int = Field(ge=1, le=365)

@app.put('/api/admin/retention', tags=['Administration'])
async def retention(body: Retention, user=Depends(core.actor)):
    if not user.admin:
        raise HTTPException(403, 'Somente administradores')
    await core.sql("INSERT INTO studio_settings(name,value) VALUES ('retention_days',%s) ON CONFLICT(name) DO UPDATE SET value=excluded.value", (Jsonb(body.days),))
    await core.audit(user, 'retention.update', str(body.days))
    return {'days': body.days, 'cleanup_interval_seconds': 3600}

@app.get('/openapi.json', tags=['Documentation'])
async def openapi(user=Depends(core.actor)):
    return app.openapi()

@app.get('/docs', response_class=HTMLResponse)
async def docs(user=Depends(core.actor)):
    return '<html lang="pt-BR"><meta charset="utf-8"><h1>Moara Studio · API</h1><p>Use Bearer com uma chave individual e as permissões necessárias.</p><a href="/studio/openapi.json">OpenAPI 3.1 — contrato completo para download</a><p>Documentação de uso disponível no portal, seção API.</p></html>'

@app.get('/', response_class=HTMLResponse)
async def index(request: Request):
    if 'password' in request.query_params or 'email' in request.query_params:
        return RedirectResponse('/studio/', status_code=303)
    page=(Path(__file__).parent / 'static/index.html').read_text(encoding='utf-8')
    if os.getenv('CONNECTOR_CENTER_ENABLED', 'false').lower() != 'true':
        page=re.sub(r'<a\b[^>]*class="[^"]*connector-nav[^"]*"[^>]*>.*?</a>', '', page)
    return HTMLResponse(page)

if os.getenv('CONNECTOR_CENTER_ENABLED', 'false').lower() == 'true':
    from connector_proxy import router as connector_router
    app.include_router(connector_router)
app.mount('/assets', StaticFiles(directory=Path(__file__).parent / 'static'), name='assets')
