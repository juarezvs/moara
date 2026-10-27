ARG BASE_IMAGE=ai-webui:moara-feedback-20261027
FROM ${BASE_IMAGE}
USER root
COPY automatic_documents.py /app/backend/open_webui/utils/automatic_documents.py
COPY install.py /tmp/moara-auto-documents-install.py
RUN python /tmp/moara-auto-documents-install.py && rm /tmp/moara-auto-documents-install.py
