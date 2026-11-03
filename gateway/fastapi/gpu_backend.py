"""Optional remote GPU execution with CPU recovery before output is delivered."""
import asyncio
import json
import time
import ssl

import httpx


class GPUBackend:
    def __init__(self, base_url='', models=None, embeddings=False, resident='moara-main-gpu', embedding_base_url=''):
        self.base_url = base_url.rstrip('/')
        self.models = {key.removesuffix(':latest'): value for key, value in (models or {}).items()}
        self.embeddings = embeddings
        self.resident = resident.removesuffix(':latest')
        self._ready = False
        self._check_after = 0.0
        self._probe_lock = asyncio.Lock()
        self.embedding_probe = GPUBackend(embedding_base_url, resident='embeddinggemma:300m') if embedding_base_url else None
        self.secure_client = None
        self.metrics_url = ''

    @classmethod
    def from_env(cls, env):
        instance=cls(env.get('GPU_INFERENCE_BASE_URL', ''), json.loads(env.get('GPU_MODELS_JSON', '{}')),
                   env.get('GPU_EMBEDDINGS_ENABLED', 'false').lower() == 'true',
                   env.get('GPU_RESIDENT_MODEL', 'moara-main-gpu'), env.get('GPU_EMBEDDING_BASE_URL', ''))
        if instance.base_url.startswith('https://'):
            context=ssl.create_default_context(cafile=env['GPU_TLS_CA_FILE'])
            context.minimum_version=ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(env['GPU_TLS_CERT_FILE'],env['GPU_TLS_KEY_FILE'])
            instance.secure_client=httpx.AsyncClient(verify=context,trust_env=False,
                timeout=httpx.Timeout(180,connect=3),limits=httpx.Limits(max_connections=8,max_keepalive_connections=4))
            if instance.embedding_probe:
                if not instance.embedding_probe.base_url.startswith('https://'):raise ValueError('GPU embeddings must use TLS')
                instance.embedding_probe.secure_client=instance.secure_client
            instance.metrics_url=env.get('GPU_METRICS_URL','')
            if instance.metrics_url and not instance.metrics_url.startswith('https://'):raise ValueError('GPU metrics must use TLS')
        return instance

    async def close(self):
        if self.secure_client:await self.secure_client.aclose()

    async def status(self,client):
        remote=self.secure_client or client
        result={'transport':'mutual_tls_over_ssh' if self.secure_client else 'ssh_tunnel',
                'principal_resident':await self.ready(client),'embeddings_resident':await (self.embedding_probe or self).ready(client),
                'gpu':{'available':False}}
        if self.metrics_url:
            try:
                response=await remote.get(self.metrics_url,timeout=4);response.raise_for_status()
                result['gpu']=response.json()
            except (httpx.HTTPError,ValueError):pass
        return result

    def failed(self):
        self._ready = False
        self._check_after = time.monotonic() + 10

    async def ready(self, client):
        client=self.secure_client or client
        if not self.base_url:
            return False
        if time.monotonic() < self._check_after:
            return self._ready
        async with self._probe_lock:
            if time.monotonic() < self._check_after:
                return self._ready
            try:
                response = await client.get(self.base_url + '/api/ps', timeout=2)
                response.raise_for_status()
                self._ready = any(
                    row.get('name', '').removesuffix(':latest') == self.resident
                    and row.get('size', 0) > 0 and row.get('size_vram') == row['size']
                    for row in response.json().get('models', []))
            except (httpx.HTTPError, ValueError, TypeError, KeyError):
                self._ready = False
            self._check_after = time.monotonic() + 10
            return self._ready

    async def chat(self, client, physical, cpu_upstream, data, specialist=False):
        target = None if specialist else self.models.get(physical.removesuffix(':latest'))
        backend = 'cpu'
        if self.base_url and target:
            backend = 'cpu-fallback'
            if await self.ready(client):
                remote=self.secure_client or client
                request = remote.build_request('POST', self.base_url + '/v1/chat/completions',
                                               json={**data, 'model': target},
                                               timeout=httpx.Timeout(45 if data.get('stream') else 180, connect=3))
                try:
                    response = await remote.send(request, stream=True)
                    if response.status_code not in (404, 500, 502, 503, 504):
                        return response, 'gpu'
                    await response.aclose()
                except httpx.HTTPError:
                    pass
                self.failed()
        request = client.build_request('POST', cpu_upstream + '/v1/chat/completions',
                                       json={**data, 'model': physical},
                                       timeout=httpx.Timeout(1200 if specialist else 300, connect=5))
        return await client.send(request, stream=True), backend

    async def embed(self, client, cpu_upstream, model, texts, threads):
        body = {'model': model, 'input': texts, 'truncate': False,
                'options': {'num_thread': threads, 'num_gpu': 0}}
        backend = 'cpu'
        probe = self.embedding_probe or self
        if probe.base_url and self.embeddings:
            backend = 'cpu-fallback'
            if await probe.ready(client):
                try:
                    response = await (probe.secure_client or client).post(probe.base_url + '/api/embed',
                                                 json={**body, 'options': {**body['options'], 'num_gpu': -1}},
                                                 timeout=httpx.Timeout(90, connect=3))
                    if response.status_code not in (404, 500, 502, 503, 504):
                        return response, 'gpu'
                except httpx.HTTPError:
                    pass
                probe.failed()
        return await client.post(cpu_upstream + '/api/embed', json=body), backend

    async def native_chat(self, client, cpu_upstream, model, body):
        target = self.models.get(model.removesuffix(':latest'))
        backend = 'cpu'
        if self.base_url and target:
            backend = 'cpu-fallback'
            if await self.ready(client):
                try:
                    response = await (self.secure_client or client).post(self.base_url + '/api/chat',
                                                 json={**body, 'model': target,
                                                       'options': {**body.get('options', {}), 'num_gpu': -1}},
                                                 timeout=httpx.Timeout(180, connect=3))
                    if response.status_code not in (404, 500, 502, 503, 504):
                        return response, 'gpu'
                except httpx.HTTPError:
                    pass
                self.failed()
        return await client.post(cpu_upstream + '/api/chat', json={**body, 'model': model},
                                 timeout=httpx.Timeout(600, connect=5)), backend
