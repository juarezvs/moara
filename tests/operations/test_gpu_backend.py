import importlib.util
import json
from pathlib import Path
import unittest

import httpx

path = Path(__file__).resolve().parents[2] / 'gateway/fastapi/gpu_backend.py'
spec = importlib.util.spec_from_file_location('gpu_backend', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GPURecoveryTests(unittest.IsolatedAsyncioTestCase):
    def backend(self):
        return module.GPUBackend('http://gpu', {'approved': 'moara-main-gpu'}, True)

    def readiness(self):
        return httpx.Response(200, json={'models': [{'name': 'moara-main-gpu:latest', 'size': 100, 'size_vram': 100}]})

    async def test_approved_chat_uses_gpu_and_preserves_payload(self):
        seen = []
        def handler(request):
            seen.append(request)
            return self.readiness() if request.url.path == '/api/ps' else httpx.Response(200, json={'ok': True})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response, backend = await self.backend().chat(client, 'approved', 'http://cpu', {'messages': [{'role': 'user', 'content': 'fixture'}]})
        self.assertEqual(backend, 'gpu')
        self.assertEqual(json.loads(seen[-1].content)['model'], 'moara-main-gpu')
        self.assertEqual(json.loads(seen[-1].content)['messages'][0]['content'], 'fixture')

    async def test_unapproved_model_never_reaches_gpu(self):
        seen = []
        def handler(request):
            seen.append(request.url.host)
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, backend = await self.backend().chat(client, 'other', 'http://cpu', {})
        self.assertEqual((backend, seen), ('cpu', ['cpu']))

    async def test_gpu_unavailable_recovers_on_cpu_without_changing_model(self):
        bodies = []
        def handler(request):
            if request.url.host == 'gpu':
                raise httpx.ConnectError('synthetic disconnect', request=request)
            bodies.append(json.loads(request.content))
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, backend = await self.backend().chat(client, 'approved', 'http://cpu', {'model': 'client-input'})
        self.assertEqual(backend, 'cpu-fallback')
        self.assertEqual(bodies[0]['model'], 'approved')

    async def test_failure_before_streaming_falls_back_and_opens_circuit(self):
        seen = []
        def handler(request):
            seen.append((request.url.host, request.url.path))
            if request.url.path == '/api/ps': return self.readiness()
            return httpx.Response(503 if request.url.host == 'gpu' else 200)
        router = self.backend()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            for _ in range(2):
                _, backend = await router.chat(client, 'approved', 'http://cpu', {})
                self.assertEqual(backend, 'cpu-fallback')
        self.assertEqual(sum(host == 'gpu' for host, _ in seen), 2)
        self.assertEqual(sum(host == 'cpu' for host, _ in seen), 2)

    async def test_partial_gpu_residency_is_not_ready(self):
        def handler(request):
            if request.url.path == '/api/ps':return httpx.Response(200, json={'models': [{'name': 'moara-main-gpu', 'size': 100, 'size_vram': 50}]})
            return httpx.Response(200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, backend = await self.backend().chat(client, 'approved', 'http://cpu', {})
        self.assertEqual(backend, 'cpu-fallback')

    async def test_invalid_request_is_not_retried_on_cpu(self):
        seen = []
        def handler(request):
            seen.append(request.url.host)
            return self.readiness() if request.url.path == '/api/ps' else httpx.Response(400)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            response, backend = await self.backend().chat(client, 'approved', 'http://cpu', {})
        self.assertEqual((response.status_code, backend, seen), (400, 'gpu', ['gpu', 'gpu']))

    async def test_embeddings_fallback_preserves_model_and_cpu_parameters(self):
        seen = []
        def handler(request):
            if request.url.path == '/api/ps':return self.readiness()
            seen.append((request.url.host, json.loads(request.content)))
            return httpx.Response(503 if request.url.host == 'gpu' else 200)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, backend = await self.backend().embed(client, 'http://cpu', 'embeddinggemma:300m', ['fixture'], 12)
        self.assertEqual(backend, 'cpu-fallback')
        self.assertEqual([body['model'] for _, body in seen], ['embeddinggemma:300m'] * 2)
        self.assertEqual([body['options']['num_gpu'] for _, body in seen], [-1, 0])

    async def test_backend_recovers_after_circuit_probe(self):
        healthy = False
        def handler(request):
            if request.url.host == 'gpu' and not healthy: raise httpx.ConnectError('synthetic', request=request)
            return self.readiness() if request.url.path == '/api/ps' else httpx.Response(200)
        router = self.backend()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, first = await router.chat(client, 'approved', 'http://cpu', {})
            healthy = True
            router._check_after = 0
            _, second = await router.chat(client, 'approved', 'http://cpu', {})
        self.assertEqual((first, second), ('cpu-fallback', 'gpu'))

    async def test_separate_embedding_failure_does_not_disable_primary_gpu(self):
        def handler(request):
            if request.url.host=='embedding':raise httpx.ConnectError('synthetic embedding outage',request=request)
            return self.readiness() if request.url.path=='/api/ps' else httpx.Response(200)
        router=module.GPUBackend('http://gpu',{'approved':'moara-main-gpu'},True,embedding_base_url='http://embedding')
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            _, embedding=await router.embed(client,'http://cpu','embeddinggemma:300m',['fixture'],12)
            _, primary=await router.chat(client,'approved','http://cpu',{})
        self.assertEqual((embedding,primary),('cpu-fallback','gpu'))


if __name__ == '__main__':
    unittest.main()
