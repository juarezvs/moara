#!/usr/bin/env python3
import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]
os.environ["DOCKER_HOST"] = f"unix:///run/user/{os.getuid()}/docker.sock"
with urllib.request.urlopen("https://ghcr.io/token?scope=repository:ggml-org/llama.cpp:pull&service=ghcr.io", timeout=30) as response:
    token = json.load(response)["token"]
for tag in ["server-v0.7.0", "server"]:
    request = urllib.request.Request("https://ghcr.io/v2/ggml-org/llama.cpp/manifests/" + tag, headers={"Authorization": "Bearer " + token, "Accept": "application/vnd.oci.image.index.v1+json,application/vnd.docker.distribution.manifest.list.v2+json,application/vnd.oci.image.manifest.v1+json,application/vnd.docker.distribution.manifest.v2+json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            digest = response.headers["Docker-Content-Digest"]
            manifest = json.load(response)
        break
    except urllib.error.HTTPError as exc:
        if exc.code != 404:
            raise
else:
    raise RuntimeError("No verified CPU server image")
image = "ghcr.io/ggml-org/llama.cpp:" + tag + "@" + digest
subprocess.run(["docker", "pull", image], check=True)
(root / "inference/llamacpp/image.lock").write_text(image + "\n")
version = subprocess.run(["docker", "run", "--rm", "--network", "none", image, "--version"], capture_output=True, text=True, check=True)
(root / "inference/llamacpp/version.txt").write_text(version.stdout + version.stderr)
print(image)
