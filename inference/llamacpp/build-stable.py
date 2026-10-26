#!/usr/bin/env python3
import hashlib
import io
import json
import os
import subprocess
import tarfile
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[2]
directory = Path(__file__).resolve().parent
os.environ["DOCKER_HOST"] = f"unix:///run/user/{os.getuid()}/docker.sock"
with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/v0.7.0", timeout=30) as response:
    release = json.load(response)
if release["prerelease"] or release["draft"]:
    raise ValueError("Expected stable published release")
with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/commits/v0.7.0", timeout=30) as response:
    commit = json.load(response)["sha"]
with urllib.request.urlopen("https://api.github.com/repos/ggml-org/llama.cpp/git/ref/tags/v0.7.0", timeout=30) as response:
    tag_object = json.load(response)["object"]["sha"]
with urllib.request.urlopen(release["tarball_url"], timeout=60) as response:
    archive = response.read(64 * 1024**2)
    if response.read(1):
        raise ValueError("Source archive exceeded limit")
digest = hashlib.sha256(archive).hexdigest()
with tarfile.open(fileobj=io.BytesIO(archive)) as contents:
    prefix = contents.getmembers()[0].name
if not any(prefix.endswith(sha[:7]) for sha in [commit, tag_object]):
    raise ValueError("Archive prefix does not match the release tag or peeled commit")
(directory / "source.tar.gz").write_bytes(archive)
env = dict(line.split("=", 1) for line in (root / "infrastructure/.env").read_text().splitlines() if "=" in line)
image = "ai-llamacpp-server:0.7.0"
subprocess.run(["docker", "build", "--build-arg", "PYTHON_IMAGE=" + env["PYTHON_IMAGE"], "--build-arg", "SOURCE_SHA256=" + digest, "--build-arg", "SOURCE_COMMIT=" + commit, "-t", image, str(directory)], check=True)
image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
(directory / "image.lock").write_text(image_id + "\n")
version = subprocess.run(["docker", "run", "--rm", "--network", "none", image_id, "--version"], check=True, capture_output=True, text=True)
(directory / "version.txt").write_text(version.stdout + version.stderr)
(directory / "source.lock.json").write_text(json.dumps({"release": release["tag_name"], "release_tag_object": tag_object, "source_commit": commit, "archive_prefix": prefix, "url": release["html_url"], "tarball_url": release["tarball_url"], "source_sha256": digest, "image_id": image_id, "native_cpu": "Xeon Silver 4214; rebuild before moving to a different CPU"}, indent=2))
print("STABLE_LLAMA_BUILD_OK", image_id)
