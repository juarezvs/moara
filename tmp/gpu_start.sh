set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends nvidia-utils-595-server
docker run --rm --gpus all --entrypoint nvidia-smi ollama/ollama:0.40.6@sha256:265409e1d931028a8f7d5a32bcbafddd7bffbc6cc629d77efe9560adf692a5e7
iptables -C DOCKER-USER -p tcp -m conntrack --ctorigdst 172.19.5.246 --ctorigdstport 11435 ! -s 172.19.5.250 -j DROP 2>/dev/null || iptables -I DOCKER-USER 1 -p tcp -m conntrack --ctorigdst 172.19.5.246 --ctorigdstport 11435 ! -s 172.19.5.250 -j DROP
docker run -d --name moara-gpu-validation --gpus all --restart no --memory 24g --memory-swap 24g --cpus 20 --pids-limit 512 --security-opt no-new-privileges:true -p 172.19.5.246:11435:11434 -v /home/nutec/moara-gpu-validation:/root/.ollama -e OLLAMA_NO_CLOUD=1 -e OLLAMA_NUM_PARALLEL=1 -e OLLAMA_MAX_LOADED_MODELS=1 -e OLLAMA_CONTEXT_LENGTH=8192 -e OLLAMA_KEEP_ALIVE=5m ollama/ollama:0.40.6@sha256:265409e1d931028a8f7d5a32bcbafddd7bffbc6cc629d77efe9560adf692a5e7
