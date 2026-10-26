FROM ai-gateway:1.0.0
USER root
COPY requirements.txt /tmp/studio-requirements.txt
COPY requirements.lock /tmp/studio-requirements.lock
RUN pip install --no-cache-dir -r /tmp/studio-requirements.txt -c /tmp/studio-requirements.lock \
    && mkdir -p /data && chown -R 10001:10001 /data
WORKDIR /app/studio
COPY . .
USER 10001:10001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log", "--proxy-headers"]
