import json
import time
import threading
from flask import Flask, render_template, request

from gevent import monkey
from geventwebsocket import WebSocketError

monkey.patch_all()

app = Flask(__name__)

esp_client = None
browser_clients = set()
esp_last_seen = 0
ESP_TIMEOUT = 30
lock = threading.Lock()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/ws")
def ws():
    global esp_client, esp_last_seen

    if not request.environ.get("wsgi.websocket"):
        return "WebSocket required", 400

    ws = request.environ["wsgi.websocket"]
    role = None

    print("WS CONNECTED")

    try:
        while True:
            data = ws.receive()
            if not data:
                break

            obj = json.loads(data)

            # ESP heartbeat
            if "hb" in obj:
                with lock:
                    esp_client = ws
                    esp_last_seen = time.time()
                role = "esp"
                print("ESP REGISTERED")
                continue

            # Browser command
            if "cmd" in obj:
                with lock:
                    browser_clients.add(ws)
                role = "browser"

                if esp_client:
                    esp_client.send(data)
                continue

            # Telemetry
            if ws == esp_client:
                esp_last_seen = time.time()
                dead = []
                for b in list(browser_clients):
                    try:
                        b.send(data)
                    except:
                        dead.append(b)
                for d in dead:
                    browser_clients.discard(d)

    except WebSocketError:
        pass

    finally:
        print("WS DISCONNECTED")
        with lock:
            browser_clients.discard(ws)
            if ws == esp_client:
                esp_client = None

    return ""
