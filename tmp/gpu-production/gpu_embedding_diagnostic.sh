systemctl show moara-gpu-warm.service -p ActiveState -p Result
journalctl -u moara-gpu-warm.service -n 12 --no-pager
docker logs moara-gpu-ollama 2>&1 | grep -E 'embeddinggemma|offload|gpu memory|library=CUDA|library=cpu' | tail -40
