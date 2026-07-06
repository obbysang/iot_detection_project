#!/usr/bin/env python3
import time
import random
import json
import urllib.request
import subprocess
import sys

BROKER = "192.168.50.10"
WEB_URL = "http://192.168.50.11"

try:
    import paho.mqtt.client as mqtt
    HAS_MQTT = True
except ImportError:
    HAS_MQTT = False

def publish_mqtt(temp):
    if not HAS_MQTT:
        return
    try:
        client = mqtt.Client()
        client.connect(BROKER, 1883, 5)
        client.publish("sensors/temperature", json.dumps({"temp": temp}))
        client.disconnect()
    except Exception:
        pass

def http_get():
    try:
        urllib.request.urlopen(WEB_URL, timeout=2)
    except Exception:
        pass

def icmp_ping():
    try:
        subprocess.run(
            ["ping", "-c", "1", "-W", "1", WEB_URL],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
        )
    except Exception:
        pass

if __name__ == "__main__":
    while True:
        temp = random.randint(20, 30)
        publish_mqtt(temp)

        if random.random() < 0.30:
            http_get()

        if random.random() < 0.10:
            icmp_ping()

        time.sleep(random.uniform(3, 8))
