docker exec moara-gpu-embeddings ollama ps
docker exec moara-gpu-ollama ollama ps
docker logs --tail 8 moara-gpu-ollama 2>&1
docker logs --tail 5 moara-gpu-embeddings 2>&1
systemctl show moara-gpu.service -p ActiveState -p SubState -p Result
