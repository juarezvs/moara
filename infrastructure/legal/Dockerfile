ARG BASE_IMAGE=moara-core:pre-legal-20261030
FROM ${BASE_IMAGE}
COPY moara/legal_mcp /app/moara/legal_mcp
COPY moara/gateway/legal_verification.py moara/gateway/chat_api.py moara/gateway/platform_runs.py moara/gateway/api.py /app/moara/gateway/
COPY moara/gateway/migrations/006_legal_evidence.sql /app/moara/gateway/migrations/
COPY moara/gateway/alembic/versions/0006_legal_evidence.py /app/moara/gateway/alembic/versions/
COPY moara/gateway/migrations/007_legal_evidence_guard.sql /app/moara/gateway/migrations/
COPY moara/gateway/alembic/versions/0007_legal_evidence_guard.py /app/moara/gateway/alembic/versions/
COPY moara/web/dist/moara-web/browser /app/web
