set -eu
docker restart moara-gpu-validation
docker inspect moara-gpu-validation --format '{{.State.Status}}'
