#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(realpath "$0")")/../.."
umask 077
export DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock"
exec flock -n backups/.lock python3 moara/infrastructure/scripts/preservation.py backup-and-verify
