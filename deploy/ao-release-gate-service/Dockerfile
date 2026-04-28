FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WEB_CONCURRENCY=1 \
    WEB_THREADS=4 \
    WEB_TIMEOUT=30

WORKDIR /app

COPY README.md pyproject.toml ./
COPY ao_kernel ./ao_kernel

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[release-gate-service]" \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin ao-kernel

USER 10001

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8000'), timeout=3).read()"

CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8000} --workers ${WEB_CONCURRENCY:-1} --threads ${WEB_THREADS:-4} --timeout ${WEB_TIMEOUT:-30} ao_kernel.ao_release_gate_runtime:application"]
