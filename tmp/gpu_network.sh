iptables -nvL DOCKER-USER
iptables -nvL FORWARD
ss -lnt | grep 11435
docker logs --tail 12 moara-gpu-validation
