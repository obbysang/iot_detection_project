FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    ca-certificates \
    curl \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends docker-ce-cli \
    && rm -rf /var/lib/apt/lists/*

COPY ml/requirements.txt /tmp/requirements-ml.txt
RUN pip install --default-timeout=300 --no-cache-dir -r /tmp/requirements-ml.txt

COPY dashboard/server/requirements.txt /tmp/requirements-server.txt
RUN pip install --default-timeout=300 --no-cache-dir -r /tmp/requirements-server.txt

CMD ["uvicorn", "dashboard.server.main:app", "--host", "0.0.0.0", "--port", "8000"]
