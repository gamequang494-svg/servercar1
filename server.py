import asyncio
import json
import time
import os
from flask import Flask, render_template
from websockets.exceptions import ConnectionClosed
from websockets.asyncio.server import serve
from websockets.http import Headers
from werkzeug.serving import run_simple

# ================= FLASK APP =================

flask_app = Flask(__name__)

@flask_app.route("/")
def index():
    return """
    <h2>RC CAR SERVER READY</h2>
    <script>
    let ws = new WebSocket("wss://" + location.host + "/ws");

    ws.onopen = () => console.log("WS Connected");
    ws.onmessage = e => console.log("Received:", e.data);
    ws.onclose = () => console.log("WS Closed");
    </script>
    """

# ================= WS STATE =================

esp_client = None
browser_clients = set()
esp_last_seen = 0
lock = asyncio.Lock()

# ================= WS HANDLER =================

async def ws_handler(websocket):
    global esp_client, esp_last_seen

    print("WS CONNECTED")

    try:
        async for message in websocket:
            data = json.loads(message)

            # ESP heartbeat
            if "hb" in data:
                async with lock:
                    esp_client = websocket
                    esp_last_seen = time.time()
                continue

            # ESP telemetry
            if websocket == esp_client:
                esp_last_seen = time.time()
                dead = []
                for b in browser_clients:
                    try:
                        await b.send(message)
                    except:
                        dead.append(b)
                for b in dead:
                    browser_clients.discard(b)
                continue

            # Browser command
            browser_clients.add(websocket)
            if esp_client:
                await esp_client.send(message)

    except ConnectionClosed:
        pass

    finally:
        print("WS DISCONNECTED")
        browser_clients.discard(websocket)
        if websocket == esp_client:
            async with lock:
                esp_client = None

# ================= WATCHDOG =================

async def watchdog():
    global esp_client
    while True:
        await asyncio.sleep(5)
        async with lock:
            if esp_client and (time.time() - esp_last_seen > 20):
                print("ESP TIMEOUT")
                esp_client = None

# ================= ASGI WRAPPER =================

async def asgi_app(scope, receive, send):
    if scope["type"] == "http":
        await flask_app(scope, receive, send)

    elif scope["type"] == "websocket":
        if scope["path"] == "/ws":
            await ws_handler(scope["websocket"])
        else:
            await send({"type": "websocket.close"})

# ================= MAIN =================

async def main():
    port = int(os.environ.get("PORT", 10000))
    asyncio.create_task(watchdog())

    async with serve(
        ws_handler,
        "0.0.0.0",
        port,
        compression=None,
        ping_interval=20,
        ping_timeout=20
    ):
        print("SERVER READY")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(main())
