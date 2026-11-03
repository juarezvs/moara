docker logs --tail 280 moara-gpu-ollama 2>&1 | grep -E 'memory|gpu|GPU|CUDA|layer|batch|threads|devices|backend|parallel|fit|server.go' | tail -85
