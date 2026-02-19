import json
import threading
import time
import os
from quart import Quart, render_template
from flask_sock import Sock

app = Flask(__name__)
sock = Sock(app)

# ================= STATE =================

class ServerState:
    def __init__(self):
        self.esp_client = None
        self.browser_clients = set()
        self.esp_last_seen = 0
        self.lock = threading.Lock()

state = ServerState()

ESP_TIMEOUT = 30


# ================= ROUTE =================

@app.route("/")
def index():
    return render_template("index.html")


# ================= UTIL =================

def broadcast_to_browsers(message):
    dead = []

    with state.lock:
        clients = list(state.browser_clients)

    for ws in clients:
        try:
            ws.send(message)
        except:
            dead.append(ws)

    if dead:
        with state.lock:
            for ws in dead:
                state.browser_clients.discard(ws)


def send_to_esp(message):
    with state.lock:
        esp = state.esp_client

    if esp:
        try:
            esp.send(message)
        except:
            print("ESP send failed")


# ================= WEBSOCKET =================

@sock.route("/ws")
def websocket(ws):

    role = None

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
            if obj.get("hb"):
                with state.lock:
                    state.esp_client = ws
                    state.esp_last_seen = time.time()

                role = "esp"
                print("ESP REGISTERED")
                continue

            # ===== BROWSER COMMAND =====
            if obj.get("cmd"):
                with state.lock:
                    state.browser_clients.add(ws)

                role = "browser"
                send_to_esp(data)
                continue

            # ===== TELEMETRY FROM ESP =====
            with state.lock:
                if ws == state.esp_client:
                    state.esp_last_seen = time.time()

            if role == "esp":
                broadcast_to_browsers(data)

    except Exception as e:
        print("WS ERROR:", e)

    finally:
        print("WS DISCONNECTED")

        with state.lock:
            state.browser_clients.discard(ws)

            if ws == state.esp_client:
                state.esp_client = None


# ================= WATCHDOG =================

def esp_watchdog():
    while True:
        time.sleep(5)

        with state.lock:
            if (
                state.esp_client and
                (time.time() - state.esp_last_seen > ESP_TIMEOUT)
            ):
                print("ESP TIMEOUT")
                state.esp_client = None


threading.Thread(target=esp_watchdog, daemon=True).start()


# ================= RUN =================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"RC CAR WS Server running on port {port}")
    app.run(host="0.0.0.0", port=port)

