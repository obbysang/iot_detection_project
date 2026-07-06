#!/bin/bash
mkdir -p /var/run/sshd
/usr/sbin/sshd -D &
python3 /scripts/normal_traffic.py &
wait
