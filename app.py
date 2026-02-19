import json
import threading
import time
from flask import Flask, render_template
from flask_sock import Sock
import os
app = Flask(__name__)
sock = Sock(app)

esp_client = None
browser_clients = set()
esp_last_seen = 0
lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


# ================= BROADCAST =================

def broadcast_to_browsers(message):
    dead = []
    for ws in browser_clients:
        try:
            ws.send(message)
        except:
            dead.append(ws)

    for ws in dead:
        browser_clients.discard(ws)


def send_to_esp(message):
    global esp_client
    if esp_client:
        try:
            esp_client.send(message)
        except:
            print("ESP send failed")


# ================= WEBSOCKET =================

@sock.route("/ws")
def websocket(ws):
    global esp_client, esp_last_seen

    print("WS CONNECTED")

    role = None

    try:
        while True:

            data = ws.receive()
            if data is None:
                break

            obj = json.loads(data)

            # ===== ESP HEARTBEAT =====
            if "hb" in obj:
                print("ESP REGISTERED")

                with lock:
                    esp_client = ws
                    esp_last_seen = time.time()

                role = "esp"
                continue

            # ===== BROWSER COMMAND =====
            if "cmd" in obj:
                if ws not in browser_clients:
                    browser_clients.add(ws)

                role = "browser"

                send_to_esp(data)
                continue

            # ===== TELEMETRY FROM ESP =====
            if ws == esp_client:
                broadcast_to_browsers(data)

    except Exception as e:
        print("WS ERROR:", e)

    finally:
        print("WS DISCONNECTED")

        browser_clients.discard(ws)

        if ws == esp_client:
            with lock:
                esp_client = None

# ================= ESP WATCHDOG =================

def esp_watchdog():
    global esp_client

    while True:
        time.sleep(5)

        with lock:
            if esp_client and (time.time() - esp_last_seen > 20):
                print("ESP TIMEOUT")
                esp_client = None


threading.Thread(target=esp_watchdog, daemon=True).start()


# ================= RUN =================

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    print(f"RC CAR WS Server running on port {port}")
    app.run(host="0.0.0.0", port=port)
