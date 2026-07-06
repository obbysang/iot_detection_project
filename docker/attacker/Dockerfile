FROM kalilinux/kali-rolling

RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    hydra \
    curl \
    netcat-openbsd \
    python3 \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /usr/share/wordlists
COPY wordlist.txt /usr/share/wordlists/lab_passwords.txt

WORKDIR /root
CMD ["sleep", "infinity"]
