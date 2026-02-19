import asyncio
import json
import time
import os
from websockets.server import serve
from websockets.exceptions import ConnectionClosed

esp_client = None
browser_clients = set()
esp_last_seen = 0
lock = asyncio.Lock()


async def broadcast_to_browsers(message):
    dead = []
    for ws in browser_clients:
        try:
            await ws.send(message)
        except:
            dead.append(ws)

    for ws in dead:
        browser_clients.discard(ws)


async def send_to_esp(message):
    global esp_client
    if esp_client:
        try:
            await esp_client.send(message)
        except:
            pass


async def ws_handler(websocket):
    global esp_client, esp_last_seen

    print("WS CONNECTED")

    try:
        async for message in websocket:
            data = json.loads(message)

            # ===== ESP HEARTBEAT =====
            if "hb" in data:
                async with lock:
                    esp_client = websocket
                    esp_last_seen = time.time()
                continue

            # ===== TELEMETRY FROM ESP =====
            if websocket == esp_client:
                esp_last_seen = time.time()
                await broadcast_to_browsers(message)
                continue

            # ===== BROWSER COMMAND =====
            browser_clients.add(websocket)
            await send_to_esp(message)

    except ConnectionClosed:
        pass

    finally:
        print("WS DISCONNECTED")
        browser_clients.discard(websocket)

        if websocket == esp_client:
            async with lock:
                esp_client = None


async def watchdog():
    global esp_client
    while True:
        await asyncio.sleep(5)
        async with lock:
            if esp_client and (time.time() - esp_last_seen > 20):
                print("ESP TIMEOUT")
                esp_client = None


async def main():
    port = int(os.environ.get("PORT", 10000))

    asyncio.create_task(watchdog())

    async with serve(
        ws_handler,
        "0.0.0.0",
        port,
        compression=None,      # 🔥 QUAN TRỌNG – TẮT compression
        max_size=2**20,
        ping_interval=20,
        ping_timeout=20
    ):
        print("WS SERVER READY")
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
