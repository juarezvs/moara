#!/usr/bin/env python3
"""Preliminary controlled-prompt comparison; leaves the stable backend unchanged."""
import json
import os
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parents[2]
os.environ["DOCKER_HOST"] = f"unix:///run/user/{os.getuid()}/docker.sock"
dc = ["docker", "compose", "--env-file", str(root / "infrastructure/.env"), "-f", str(root / "infrastructure/docker-compose.yml")]
env = dict(line.split("=", 1) for line in (root / "infrastructure/.env").read_text().splitlines() if "=" in line)
image = (root / "inference/llamacpp/image.lock").read_text().strip()
child = r'''
import json,sys,time,urllib.request
base=sys.argv[1]
p={'model':'ai-coder-8k','messages':[{'role':'user','content':'Write a Python function that returns the union of overlapping integer intervals. Include one example.'}],'stream':True,'stream_options':{'include_usage':True},'max_tokens':128,'temperature':0}
start=time.monotonic(); first=None; usage={}; timings={}; parts=[]
with urllib.request.urlopen(urllib.request.Request(base+'/v1/chat/completions',data=json.dumps(p).encode(),headers={'Content-Type':'application/json'}),timeout=300) as response:
    for raw in response:
        line=raw.decode().strip()
        if not line.startswith('data:') or line[5:].strip()=='[DONE]': continue
        event=json.loads(line[5:])
        for choice in event.get('choices',[]):
            text=choice.get('delta',{}).get('content','') or ''
            if text and first is None: first=time.monotonic()-start
            parts.append(text)
        if event.get('usage'): usage=event['usage']
        if event.get('timings'): timings=event['timings']
elapsed=time.monotonic()-start
print(json.dumps({'total_seconds':elapsed,'ttft_seconds':first,'usage':usage,'timings':timings,'end_to_end_generation_tokens_per_second':usage.get('completion_tokens',0)/(elapsed-first) if first is not None and elapsed>first else None,'output':''.join(parts)}))
'''


def measure(base):
    r = subprocess.run(dc + ["exec", "-T", "gateway", "python", "-c", child, base], check=True, capture_output=True, text=True, timeout=360)
    return json.loads(r.stdout)


result = {"scope": "one synthetic prompt, 128 output tokens, 8K context, 12 threads; preliminary, not a quality benchmark", "stable_backend_changed": False, "results": []}
result["results"].append({"backend": "ollama", **measure("http://ollama:11434")})
model_reader = "import json; from pathlib import Path; m=json.loads(Path('/models/models/manifests/registry.ollama.ai/library/qwen3-coder/30b-a3b-q4_K_M').read_text()); d=next(l['digest'] for l in m['layers'] if l['mediaType']=='application/vnd.ollama.image.model'); p=Path('/models/models/blobs')/d.replace(':','-'); assert p.open('rb').read(4)==b'GGUF'; print(str(p))"
read = subprocess.run(["docker", "run", "--rm", "--network", "none", "--mount", "type=volume,src=ai-server_ollama,dst=/models,readonly", env["PYTHON_IMAGE"], "python", "-c", model_reader], check=True, capture_output=True, text=True)
model_path = read.stdout.strip()
container = "ai-llama-comparison"
try:
    subprocess.run(["docker", "run", "-d", "--name", container, "--network", "ai-server_inference", "--network-alias", "llama-comparison", "--read-only", "--tmpfs", "/tmp:size=128m", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory", "96g", "--cpus", "44", "--pids-limit", "512", "--mount", "type=volume,src=ai-server_ollama,dst=/models,readonly", image, "-m", model_path, "--host", "0.0.0.0", "--port", "8081", "-c", "8192", "-t", "12", "-tb", "12", "-ngl", "0", "--parallel", "1", "--alias", "ai-coder-8k", "--numa", "distribute"], check=True, stdout=subprocess.DEVNULL)
    ready = False
    for _ in range(90):
        check = subprocess.run(dc + ["exec", "-T", "gateway", "python", "-c", "import urllib.request; urllib.request.urlopen('http://llama-comparison:8081/health',timeout=3)"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if check.returncode == 0:
            ready = True; break
        time.sleep(2)
    if not ready:
        raise RuntimeError("llama server did not become healthy")
    result["results"].append({"backend": "llama.cpp", "numa": "distribute", "image": image, **measure("http://llama-comparison:8081")})
finally:
    logs = subprocess.run(["docker", "logs", container], capture_output=True, text=True)
    (root / "docs/runtime/llamacpp-comparison.log").write_text(logs.stdout + logs.stderr)
    subprocess.run(["docker", "rm", "-f", container], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (root / "docs/runtime/backend-comparison.json").write_text(json.dumps(result, indent=2))
print(json.dumps({"results": [{k:v for k,v in r.items() if k!='output'} for r in result['results']]}, indent=2))
