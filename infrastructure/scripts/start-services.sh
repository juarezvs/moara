#!/usr/bin/env bash
# Start the complete installed stack without rebuilding or recreating containers.
set -Eeuo pipefail
umask 077
cd "$(dirname "$(realpath "$0")")/../.."
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
exec flock -w 900 backups/.lock sh moara/infrastructure/scripts/compose.sh \
  up -d --no-recreate --no-build --pull never --wait --wait-timeout 900
