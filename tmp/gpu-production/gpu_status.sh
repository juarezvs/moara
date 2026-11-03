systemctl show moara-gpu.service -p ActiveState -p SubState -p Result
journalctl -u moara-gpu.service -n 15 --no-pager
docker ps --format '{{.Names}} {{.Status}}'
docker exec moara-gpu-ollama ollama ps
nvidia-smi --query-gpu=memory.used,utilization.gpu,temperature.gpu,power.draw --format=csv
