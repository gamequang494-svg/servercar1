from flask import Flask
from flask_sock import Sock
import json
import time
import threading

app = Flask(__name__)
sock = Sock(app)

esp_client = None
browser_clients = set()
esp_last_seen = 0

@app.route("/")
def health():
    return "OK", 200

@sock.route("/ws")
def websocket(ws):
    global esp_client, esp_last_seen

    print("WS CONNECTED")

    while True:
        data = ws.receive()
        if data is None:
            break

        msg = json.loads(data)

        # ESP heartbeat
        if "hb" in msg:
            esp_client = ws
            esp_last_seen = time.time()
            continue

        # ESP telemetry
        if ws == esp_client:
            esp_last_seen = time.time()
            for b in list(browser_clients):
                try:
                    b.send(data)
                except:
                    browser_clients.discard(b)
            continue

        # Browser command
        browser_clients.add(ws)
        if esp_client:
            esp_client.send(data)

    print("WS DISCONNECTED")
    browser_clients.discard(ws)
    if ws == esp_client:
        esp_client = None

def watchdog():
    global esp_client
    while True:
        time.sleep(5)
        if esp_client and (time.time() - esp_last_seen > 20):
            print("ESP TIMEOUT")
            esp_client = None

threading.Thread(target=watchdog, daemon=True).start()
