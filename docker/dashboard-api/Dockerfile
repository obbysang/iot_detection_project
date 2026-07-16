FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY ml/requirements.txt /tmp/requirements-ml.txt
COPY ml/wheels /tmp/wheels
RUN pip install --no-index --find-links=/tmp/wheels -r /tmp/requirements-ml.txt

COPY dashboard/server/requirements.txt /tmp/requirements-server.txt
RUN pip install --default-timeout=300 --no-cache-dir -r /tmp/requirements-server.txt

CMD ["uvicorn", "dashboard.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
