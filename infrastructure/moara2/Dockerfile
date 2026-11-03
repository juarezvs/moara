ARG BASE_IMAGE=moara-core:pre-moara2-20261030
FROM ${BASE_IMAGE}
COPY moara/identity /app/moara/identity
COPY moara/assistants /app/moara/assistants
COPY moara/gateway/api.py moara/gateway/chat_api.py moara/gateway/history_api.py moara/gateway/platform_runs.py moara/gateway/assistants.py moara/gateway/orchestration.py moara/gateway/official_integrations.py moara/gateway/chat_evidence.py /app/moara/gateway/
COPY moara/gateway/data_chat.py /app/moara/gateway/
COPY moara/gateway/settings.py /app/moara/gateway/
COPY moara/gateway/legal_verification.py /app/moara/gateway/
COPY moara/gateway/accessibility_api.py /app/moara/gateway/
COPY moara/gateway/inference_status.py /app/moara/gateway/
COPY moara/gateway/platform_documents.py moara/gateway/xlsx_documents.py /app/moara/gateway/
COPY moara/gateway/migrations/008_official_assistants.sql moara/gateway/migrations/009_chat_assistant_context.sql /app/moara/gateway/migrations/
COPY moara/gateway/alembic/versions/0008_official_assistants.py moara/gateway/alembic/versions/0009_chat_assistant_context.py /app/moara/gateway/alembic/versions/
COPY moara/web/dist/moara-web/browser /app/web
