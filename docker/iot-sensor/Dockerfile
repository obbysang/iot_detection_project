FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-server \
    mosquitto-clients \
    curl \
    cron \
    openssl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir paho-mqtt

RUN useradd -m iotuser && echo 'iotuser:iotpass123' | chpasswd

RUN mkdir -p /var/run/sshd && \
    sed -i 's/#PermitEmptyPasswords no/PermitEmptyPasswords no/' /etc/ssh/sshd_config && \
    sed -i 's/#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 22

ENTRYPOINT ["/entrypoint.sh"]
