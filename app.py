import json
import time
import os

from flask import Flask, render_template, jsonify
from flask_sock import Sock

from gevent import monkey
from gevent.lock import Semaphore
import gevent

# Patch standard lib for non-blocking
monkey.patch_all()

app = Flask(__name__)
sock = Sock(app)

# ================= STATE =================

esp_client = None
browser_clients = set()

esp_last_seen = 0

viewer_active = False
viewer_last_touch = 0

VIEWER_TIMEOUT = 600
ESP_TIMEOUT = 20

state_lock = Semaphore()

# ================= VIEWER =================

def update_viewer_state():
    global viewer_active
    if viewer_active and (time.time() - viewer_last_touch > VIEWER_TIMEOUT):
        viewer_active = False


@app.route("/touch", methods=["POST"])
def touch():
    global viewer_active, viewer_last_touch
    viewer_active = True
    viewer_last_touch = time.time()
    return "ok"


@app.route("/viewer_status")
def viewer_status():
    update_viewer_state()
    return jsonify({"active": viewer_active})


# ================= INDEX =================

@app.route("/")
def index():
    return render_template("index.html")


# ================= BROADCAST =================

def broadcast_to_browsers(message):
    dead = []

    # copy set để tránh mutate khi loop
    for ws in list(browser_clients):
        try:
            ws.send(message)
        except:
            dead.append(ws)

    for ws in dead:
        browser_clients.discard(ws)


def send_to_esp(message):
    global esp_client

    if not esp_client:
        return

    try:
        esp_client.send(message)
    except:
        pass


# ================= WEBSOCKET =================

@sock.route("/ws")
def websocket(ws):
    global esp_client, esp_last_seen

    print("WS CONNECTED")

    try:
        while True:
            data = ws.receive()
            if data is None:
                break

            try:
                obj = json.loads(data)
            except:
                continue

            # ===== ESP HEARTBEAT =====
            if "hb" in obj:
                with state_lock:
                    esp_client = ws
                    esp_last_seen = time.time()

                continue

            # ===== ESP TELEMETRY =====
            if ws == esp_client:
                with state_lock:
                    esp_last_seen = time.time()

                broadcast_to_browsers(data)
                continue

            # ===== BROWSER COMMAND =====
            if "cmd" in obj:
                browser_clients.add(ws)
                send_to_esp(data)
                continue

    except Exception as e:
        print("WS ERROR:", e)

    finally:
        print("WS DISCONNECTED")

        browser_clients.discard(ws)

        with state_lock:
            if ws == esp_client:
                esp_client = None


# ================= ESP WATCHDOG (GEVENT) =================

def esp_watchdog():
    global esp_client

    while True:
        gevent.sleep(2)

        with state_lock:
            if esp_client and (time.time() - esp_last_seen > ESP_TIMEOUT):
                print("ESP TIMEOUT")
                esp_client = None


gevent.spawn(esp_watchdog)


# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"RC CAR WS Server running on port {port}")
    app.run(host="0.0.0.0", port=port)
