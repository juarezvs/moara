set -eu
cat /proc/sys/kernel/random/boot_id
systemctl is-enabled moara-gpu.service moara-gpu-warm.timer
systemctl is-active moara-gpu.service moara-gpu-warm.timer
systemctl show moara-gpu-warm.service -p Result
docker ps --format '{{.Names}} {{.Status}}'
docker exec moara-gpu-ollama ollama ps
docker exec moara-gpu-embeddings ollama ps
nvidia-smi --query-gpu=name,memory.used,memory.total,temperature.gpu,power.draw --format=csv
ss -lnt | grep -E '11434|11435'
