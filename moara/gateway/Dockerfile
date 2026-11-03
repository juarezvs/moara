ARG MOARA_RUNTIME_IMAGE=ai-gateway:runtime-20261020
FROM ${MOARA_RUNTIME_IMAGE}
USER root
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por poppler-utils git \
    && dpkg-query -W tesseract-ocr tesseract-ocr-por poppler-utils git > /opt/moara-document-packages.txt \
    && rm -rf /var/lib/apt/lists/*
COPY moara/gateway/wheels /tmp/moara-wheels
COPY moara/gateway/requirements.lock /tmp/moara-requirements.lock
RUN python -m pip install --no-index --find-links=/tmp/moara-wheels --require-hashes -r /tmp/moara-requirements.lock \
    && rm -rf /tmp/moara-wheels /tmp/moara-requirements.lock \
    && mkdir -p /data && chown 10001:10001 /data
WORKDIR /app
COPY moara/__init__.py /app/moara/__init__.py
COPY moara/identity /app/moara/identity
COPY moara/legal_mcp /app/moara/legal_mcp
COPY moara/assistants /app/moara/assistants
COPY moara/gateway/*.py /app/moara/gateway/
COPY moara/gateway/alembic /app/moara/gateway/alembic
COPY moara/gateway/migrations /app/moara/gateway/migrations
COPY moara/gateway/alembic.ini /app/moara/gateway/alembic.ini
COPY moara/web/dist/moara-web/browser /app/web
USER 10001:10001
CMD ["uvicorn","moara.gateway.main:app","--host","0.0.0.0","--port","8075","--workers","1","--no-access-log","--proxy-headers"]
