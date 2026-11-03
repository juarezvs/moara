#!/bin/sh
set -eu
cd "$(dirname "$0")/../../.."
exec docker compose --env-file infrastructure/.env \
 -f infrastructure/docker-compose.yml \
 -f moara/infrastructure/compose.yml \
 -f connectors/deployment/runtime-compose.yml \
 -f moara/infrastructure/secp-rbac-compose.yml \
 -f moara/infrastructure/observability-compose.yml \
 -f moara/infrastructure/public-site-compose.yml \
 -f moara/infrastructure/platform-compose.yml \
 -f moara/infrastructure/chat-feedback-compose.yml "$@"
