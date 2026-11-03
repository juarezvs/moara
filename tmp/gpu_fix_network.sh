set -eu
docker stop moara-gpu-validation
iptables -I DOCKER-USER 1 -p tcp -m conntrack --ctdir ORIGINAL --ctorigdst 172.19.5.246 --ctorigdstport 11435 ! -s 172.19.5.250 -j DROP
iptables -D DOCKER-USER -p tcp -m conntrack --ctorigdst 172.19.5.246 --ctorigdstport 11435 ! -s 172.19.5.250 -j DROP
