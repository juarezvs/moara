import base64
import hashlib
import ipaddress
import json
import os
import re
import socket
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import psycopg
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

DATA = Path('/data')
DB_PASSWORD = Path('/run/secrets/db_password').read_text().strip()
SERVICE_KEY = Path('/run/secrets/studio_key').read_text().strip()
RENDERER_KEY = Path('/run/secrets/studio_renderer_key').read_text().strip()
CRYPTO = Fernet(base64.urlsafe_b64encode(hashlib.sha256(Path('/run/secrets/studio_crypto_key').read_bytes()).digest()))
MODULES = {'design', 'images', 'vision', 'browser', 'manuals', 'chat'}
HTTP = None

async def sql(statement, params=(), *, one=False):
    async with await psycopg.AsyncConnection.connect(host='postgres', dbname='ai', user='ai_app',
            password=DB_PASSWORD, autocommit=True, row_factory=dict_row) as connection:
        cursor = await connection.execute(statement, params)
        if cursor.description:
            return await cursor.fetchone() if one else await cursor.fetchall()

async def initialize():
    await sql('''CREATE TABLE IF NOT EXISTS studio_jobs (
        id uuid PRIMARY KEY, owner text NOT NULL, kind text NOT NULL, status text NOT NULL,
        progress integer NOT NULL DEFAULT 0, stage text NOT NULL DEFAULT 'Na fila',
        input jsonb NOT NULL, result jsonb NOT NULL DEFAULT '{}', error text,
        cancel_requested boolean NOT NULL DEFAULT false,
        created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())''')
    await sql('CREATE INDEX IF NOT EXISTS studio_jobs_owner ON studio_jobs(owner, created_at DESC)')
    await sql('''CREATE TABLE IF NOT EXISTS studio_events (
        id bigserial PRIMARY KEY, job_id uuid REFERENCES studio_jobs(id) ON DELETE CASCADE,
        owner text NOT NULL, stage text NOT NULL, progress integer NOT NULL, created_at timestamptz DEFAULT now())''')
    await sql('''CREATE TABLE IF NOT EXISTS studio_systems (
        id uuid PRIMARY KEY, owner text NOT NULL, name text NOT NULL, settings jsonb NOT NULL,
        credentials bytea, created_at timestamptz DEFAULT now())''')
    await sql('''CREATE TABLE IF NOT EXISTS studio_sessions (
        id uuid PRIMARY KEY, owner text NOT NULL, system_id uuid REFERENCES studio_systems(id),
        mode text NOT NULL, status text NOT NULL, evidence jsonb NOT NULL DEFAULT '[]', created_at timestamptz DEFAULT now())''')
    await sql('''CREATE TABLE IF NOT EXISTS studio_audit (
        id bigserial PRIMARY KEY, owner text NOT NULL, action text NOT NULL,
        resource text NOT NULL, created_at timestamptz DEFAULT now())''')
    await sql('CREATE TABLE IF NOT EXISTS studio_permissions (owner text PRIMARY KEY, scopes jsonb NOT NULL)')
    await sql('CREATE TABLE IF NOT EXISTS studio_settings (name text PRIMARY KEY, value jsonb NOT NULL)')
    # A restarted job must not silently replay browser actions.
    await sql("UPDATE studio_jobs SET status='failed', error='Execução interrompida pelo reinício; solicite uma nova tarefa.', stage='Interrompida', updated_at=now() WHERE status='running'")
    await sql("UPDATE studio_sessions SET status='closed' WHERE status='active'")

@dataclass
class Actor:
    owner: str
    name: str
    scopes: set
    admin: bool = False

async def actor(request: Request):
    authorization = request.headers.get('authorization', '')
    cookie = request.cookies.get('studio_token')
    token = authorization[7:] if authorization.startswith('Bearer ') else cookie
    if not token or len(token) > 4096:
        raise HTTPException(401, 'Entre com sua conta do Moara AI ou use uma chave individual.')
    if cookie and not authorization and request.method not in ('GET', 'HEAD') and request.headers.get('x-studio-csrf') != '1':
        raise HTTPException(403, 'Confirmação de origem ausente')
    try:
        if token.count('.') == 2:
            response = await HTTP.get('http://webui:8080/api/v1/auths/', headers={'Authorization': 'Bearer ' + token})
            if response.status_code != 200:
                raise HTTPException(401, 'Sessão expirada')
            user = response.json()
            if user.get('role') not in ('user', 'admin'):
                raise HTTPException(403, 'Conta ainda não autorizada')
            owner = 'webui:' + user['id']
            override = await sql('SELECT scopes FROM studio_permissions WHERE owner=%s', (owner,), one=True)
            scopes = set(MODULES) if user['role'] == 'admin' or not override else set(override['scopes'])
            return Actor(owner, user['name'], scopes, user['role'] == 'admin')
        response = await HTTP.get('http://gateway:8000/v1/auth/identity', headers={'Authorization': 'Bearer ' + token})
        if response.status_code != 200:
            raise HTTPException(401, 'Chave inválida ou revogada')
        identity = response.json()
        if identity['id'] == 'webui' and request.headers.get('x-studio-user-id'):
            # Reserved service credential. Only the trusted WebUI forwards verified user identity.
            uid = request.headers['x-studio-user-id']
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', uid):
                raise HTTPException(403, 'Identidade inválida')
            owner = 'webui:' + uid
            admin = request.headers.get('x-studio-user-role') == 'admin'
            override = await sql('SELECT scopes FROM studio_permissions WHERE owner=%s', (owner,), one=True)
            scopes = set(MODULES) if admin or not override else set(override['scopes'])
            return Actor(owner, 'Conta Moara AI', scopes, admin)
        return Actor('key:' + identity['id'], identity['id'], set(identity['scopes']), identity['id'] == 'admin')
    except httpx.HTTPError:
        raise HTTPException(503, 'Serviço de autenticação indisponível') from None

def require(user, scope):
    if scope not in user.scopes:
        raise HTTPException(403, 'Sua conta não tem permissão para ' + scope)

async def audit(user, action, resource):
    await sql('INSERT INTO studio_audit(owner,action,resource) VALUES (%s,%s,%s)', (user.owner, action, resource))

async def owned_job(job_id, user):
    try:
        uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(404, 'Tarefa não encontrada')
    job = await sql('SELECT * FROM studio_jobs WHERE id=%s AND owner=%s', (job_id, user.owner), one=True)
    if not job:
        raise HTTPException(404, 'Tarefa não encontrada')
    require(user, job['kind'])
    return job

async def event(job_id, owner, stage, progress):
    await sql('UPDATE studio_jobs SET stage=%s,progress=%s,updated_at=now() WHERE id=%s', (stage, progress, job_id))
    await sql('INSERT INTO studio_events(job_id,owner,stage,progress) VALUES (%s,%s,%s,%s)', (job_id, owner, stage, progress))

def job_directory(job_id):
    identifier = str(uuid.UUID(str(job_id)))
    path = DATA / identifier
    path.mkdir(mode=0o700, exist_ok=True)
    return path

def file_path(job_id, name):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', name) or '..' in name:
        raise HTTPException(404, 'Arquivo não encontrado')
    path = job_directory(job_id) / name
    if not path.is_file():
        raise HTTPException(404, 'Arquivo não encontrado')
    return path

async def renderer(path, data=None, method='POST'):
    response = await HTTP.request(method, 'http://studio-renderer:8091' + path,
        json=data, headers={'Authorization': 'Bearer ' + RENDERER_KEY}, timeout=120)
    if response.status_code >= 400:
        raise HTTPException(response.status_code, 'Navegador: ' + str(response.json().get('detail', 'operação indisponível'))[:180])
    return response.json()

async def gateway(path, data):
    response = await HTTP.post('http://gateway:8000' + path, json=data,
        headers={'Authorization': 'Bearer ' + SERVICE_KEY}, timeout=1260)
    if response.status_code >= 400:
        raise RuntimeError('Motor local: ' + str(response.status_code) + ' · ' + str(response.json().get('detail', 'indisponível'))[:180])
    return response.json()

async def language(prompt, *, system='', json_mode=False, model='general', tokens=1100):
    body = {'model': model, 'messages': [{'role': 'system', 'content': system or 'Responda em português. Não invente fatos.'},
        {'role': 'user', 'content': prompt}], 'max_tokens': tokens, 'temperature': 0.15}
    if json_mode:
        body['response_format'] = {'type': 'json_object'}
    response = await gateway('/v1/chat/completions', body)
    return response['choices'][0]['message']['content']

def authorized_settings(base_url, extra_origins, paths, masks, allowed_fill, environment, resolved_hosts=None):
    if environment not in ('demo', 'development', 'staging'):
        raise HTTPException(403, 'A exploração de produção não está habilitada')
    origins = []
    hosts = {}
    for value in [base_url, *extra_origins]:
        parsed = urlsplit(value)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
            raise HTTPException(422, 'URL HTTP(S) válida necessária')
        try:
            addresses = resolved_hosts[parsed.hostname] if resolved_hosts is not None else sorted({item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)})
        except socket.gaierror:
            raise HTTPException(422, 'Destino não resolve no servidor') from None
        for value_ip in addresses:
            ip = ipaddress.ip_address(value_ip)
            if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
                raise HTTPException(403, 'Loopback, metadados e destinos locais especiais são bloqueados')
        hosts[parsed.hostname] = addresses
        origins.append(parsed.scheme + '://' + parsed.netloc)
    if not paths or any(not p.startswith('/') or len(p) > 200 for p in paths):
        raise HTTPException(422, 'Prefixos de navegação inválidos')
    return {'base_url': base_url, 'origins': list(dict.fromkeys(origins)), 'hosts': hosts,
        'paths': paths, 'masks': masks, 'allowed_fill': allowed_fill, 'environment': environment}
