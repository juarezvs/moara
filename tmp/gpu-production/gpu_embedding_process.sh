docker top moara-gpu-ollama -eo pid,args
docker logs --tail 350 moara-gpu-ollama 2>&1 | grep -E 'common_memory|fit|CUDA.*buffer|CPU.*buffer|--device|--gpu|--n-gpu|load_backend|starting.*server|offload|gpu memory' | tail -50
