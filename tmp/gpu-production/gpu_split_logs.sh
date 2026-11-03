docker logs moara-gpu-ollama 2>&1 | grep -v '\[GIN\]' | tail -55
docker top moara-gpu-ollama -eo pid,args
nvidia-smi
