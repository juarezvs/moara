"""Keep the primary model and unchanged embedding weights resident on the GPU."""
import json
import os
import urllib.request
from pathlib import Path

BASE = os.getenv('OLLAMA_URL', 'http://127.0.0.1:11434')
EMBED_BASE = os.getenv('OLLAMA_EMBED_URL', 'http://127.0.0.1:11435')
PRIMARY = 'moara-main-gpu:latest'


def call(path, body=None, base=BASE):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=240) as response:
        return json.load(response)


def main():
    embedding = 'embeddinggemma:300m'
    embed_loaded = {row['name']: row for row in call('/api/ps', base=EMBED_BASE)['models']}
    if embedding in embed_loaded and embed_loaded[embedding]['size_vram'] != embed_loaded[embedding]['size']:
        call('/api/embed', {'model': embedding, 'input': [], 'keep_alive': 0}, base=EMBED_BASE)
        embed_loaded = {}
    if embedding not in embed_loaded:
        call('/api/embed', {'model': embedding, 'input': ['Verificação técnica sintética de inicialização.'],
                           'keep_alive': -1, 'options': {'num_gpu': -1, 'num_thread': 12}}, base=EMBED_BASE)
    tags = {row['name'] for row in call('/api/tags')['models']}
    if PRIMARY not in tags:
        call('/api/create', {'model': PRIMARY, 'from': 'moara-63af8a56-8192-12t',
                            'parameters': {'num_gpu': -1, 'num_ctx': 8192, 'num_thread': 12}, 'stream': False})
    loaded = {row['name']: row for row in call('/api/ps')['models']}
    if PRIMARY in loaded and loaded[PRIMARY]['size_vram'] != loaded[PRIMARY]['size']:
        call('/api/generate', {'model': PRIMARY, 'keep_alive': 0, 'stream': False})
        loaded = {}
    if PRIMARY not in loaded:
        call('/api/chat', {'model': PRIMARY, 'messages': [{'role': 'user', 'content': 'Responda OK.'}],
                          'think': False, 'stream': False, 'keep_alive': -1,
                          'options': {'num_predict': 8, 'temperature': 0, 'num_gpu': -1}})
    loaded = {row['name']: row for row in call('/api/ps')['models']}
    loaded.update({row['name']: row for row in call('/api/ps', base=EMBED_BASE)['models']})
    for name in (PRIMARY, embedding):
        row = loaded[name]
        if row['size_vram'] != row['size']:
            raise RuntimeError('A required model is not fully resident on the GPU')
    if loaded[PRIMARY]['context_length'] != 8192:
        raise RuntimeError('Unexpected primary model context')
    report = {'ready': True, 'primary': PRIMARY, 'models': [
        {'name': row['name'], 'size_vram': row['size_vram'], 'context_length': row['context_length']}
        for row in loaded.values()]}
    target = Path('/run/moara-gpu/ready.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
