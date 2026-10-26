#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
cd "$(dirname "$(realpath "$0")")/../.."
[[ $EUID != 0 ]] || { echo 'Execute como nutec.'; exit 1; }
[[ $(hostname) == srvdev01-am ]] || exit 1
export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
if ! command -v dockerd-rootless-setuptool.sh >/dev/null; then
  echo 'Execute primeiro o bootstrap administrativo no terminal.'; exit 1
fi
if ! systemctl --user is-active --quiet docker; then
  dockerd-rootless-setuptool.sh install
fi
export DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
docker info --format '{{json .SecurityOptions}}' | grep -q rootless
mkdir -p inference/benchmarks backups agents/workspaces docs/runtime
python3 infrastructure/scripts/create-secrets.py
if [[ ! -s infrastructure/.env ]]; then python3 infrastructure/scripts/lock-images.py; fi
dc() { docker compose --env-file infrastructure/.env -f infrastructure/docker-compose.yml "$@"; }
general_model=$(sed -n 's/^GENERAL_MODEL=//p' infrastructure/.env | tail -n 1)
general_base=$(sed -n 's/^GENERAL_BASE_MODEL=//p' infrastructure/.env | tail -n 1)
general_model=${general_model:-ai-general-8k}
general_base=${general_base:-gemma3:12b-it-q4_K_M}
dc config --quiet
python3 infrastructure/scripts/prepare-webui-offline.py
python3 infrastructure/scripts/prepare-image-generation.py
dc pull ollama postgres
dc build gateway caddy webui image-generator
dc build studio studio-renderer studio-demo
dc --profile provision up -d seed
seed=$(dc --profile provision ps -q seed)
cleanup_seed() { dc --profile provision rm -sf seed >/dev/null 2>&1 || true; }
trap cleanup_seed EXIT
for attempt in $(seq 1 60); do
  if docker exec "$seed" ollama list >/dev/null 2>&1; then break; fi
  sleep 2
done
if [[ -s docs/runtime/model-registry.json ]]; then
  python3 infrastructure/scripts/verify-model-lock.py "$seed"
else
  models=(qwen3-coder:30b-a3b-q4_K_M qwen3:8b-q4_K_M gemma3:12b-it-q4_K_M embeddinggemma:300m)
  if [[ $general_base != gemma3:12b-it-q4_K_M ]]; then models+=("$general_base"); fi
  for model in "${models[@]}"; do docker exec "$seed" ollama pull "$model"; done
fi
specifications=('ai-coder-8k qwen3-coder:30b-a3b-q4_K_M' 'ai-fast-8k qwen3:8b-q4_K_M' 'ai-general-8k gemma3:12b-it-q4_K_M')
if [[ $general_model != ai-general-8k ]]; then specifications+=("$general_model $general_base"); fi
for specification in "${specifications[@]}"; do
  read -r name base <<< "$specification"
  printf 'FROM %s\nPARAMETER num_ctx 8192\nPARAMETER num_thread 12\nPARAMETER num_gpu 0\nPARAMETER temperature 0.2\n' "$base" | docker exec -i "$seed" sh -c 'cat > /tmp/ai.Modelfile'
  docker exec "$seed" ollama create "$name" -f /tmp/ai.Modelfile
done
docker exec "$seed" ollama list > docs/runtime/models.txt
docker exec "$seed" sh -c 'cat /root/.ollama/models/manifests/registry.ollama.ai/library/embeddinggemma/300m' > docs/runtime/embedding-manifest.json
digest=$(sha256sum docs/runtime/embedding-manifest.json | cut -d' ' -f1)
sed -i '/^EMBEDDING_VERSION=/d' infrastructure/.env
printf 'EMBEDDING_VERSION=sha256:%s\n' "$digest" >> infrastructure/.env
cleanup_seed
trap - EXIT
dc up -d --wait --wait-timeout 900
bash infrastructure/scripts/install-requested-models.sh
dc config --images > docs/runtime/images.txt
docker info --format '{{json .}}' > docs/runtime/docker-info.json
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/ai-server.service" <<EOF
[Unit]
Description=Private CPU AI services
Requires=docker.service
After=docker.service
[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$PWD
Environment=DOCKER_HOST=unix://$XDG_RUNTIME_DIR/docker.sock
ExecStart=/bin/bash $PWD/infrastructure/scripts/start-services.sh
ExecStop=/bin/sh $PWD/moara/infrastructure/scripts/compose.sh stop
TimeoutStartSec=1900
[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable --now ai-server
bash infrastructure/scripts/install-warmup.sh
caddy=$(dc ps -q caddy)
docker cp "$caddy":/data/caddy/pki/authorities/local/root.crt docs/runtime/ai-root-ca.crt
chmod 644 docs/runtime/ai-root-ca.crt
python3 infrastructure/scripts/configure-webui-models.py
dc ps
echo 'DEPLOY_OK. Certificado público: docs/runtime/ai-root-ca.crt. Credenciais em secrets/, não exibidas.'
