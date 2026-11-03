set -eu
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y --no-install-recommends docker.io docker-compose-v2 ca-certificates curl gnupg
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o /tmp/moara-nvidia-key.asc
gpg --dearmor --yes -o /usr/share/keyrings/moara-nvidia-container-toolkit.gpg /tmp/moara-nvidia-key.asc
curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/moara-nvidia-container-toolkit.gpg] https://#g' > /etc/apt/sources.list.d/moara-nvidia-container-toolkit.list
apt-get update -qq
apt-get install -y --no-install-recommends nvidia-container-toolkit
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker
docker --version
docker compose version
nvidia-ctk --version
