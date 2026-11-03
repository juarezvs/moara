docker exec moara-gpu-validation ollama ps
nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw --format=csv
docker logs --tail 75 moara-gpu-validation 2>&1
