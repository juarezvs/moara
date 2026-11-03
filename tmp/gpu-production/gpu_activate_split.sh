set -eu
systemctl restart moara-gpu.service
systemctl reset-failed moara-gpu-warm.service
systemctl start moara-gpu-warm.timer
systemctl start moara-gpu-warm.service
docker exec moara-gpu-ollama ollama ps
docker exec moara-gpu-embeddings ollama ps
nvidia-smi --query-gpu=memory.used,memory.total,temperature.gpu --format=csv
