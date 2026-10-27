ARG BASE_IMAGE
FROM ${BASE_IMAGE}
USER root
COPY moara_file_progress.py /app/backend/open_webui/retrieval/moara_file_progress.py
COPY feedback.js /app/build/static/moara/feedback.js
COPY feedback.css /app/build/static/moara/feedback.css
COPY install.py /tmp/moara-feedback-install.py
RUN python /tmp/moara-feedback-install.py && rm /tmp/moara-feedback-install.py
ENV VIEW_FILE_DEFAULT_MAX_CHARS=2000 VIEW_FILE_MAX_CHARS=4000
