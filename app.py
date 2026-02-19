import time
from flask import Flask, render_template, request
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

esp_sid = None
esp_last_seen = 0
ESP_TIMEOUT = 30


@app.route("/")
def index():
    return render_template("index.html")


@socketio.on("connect")
def on_connect():
    print("Client connected")


@socketio.on("register_esp")
def register_esp():
    global esp_sid, esp_last_seen
    esp_sid = request.sid
    esp_last_seen = time.time()
    print("ESP REGISTERED")


@socketio.on("cmd")
def handle_cmd(data):
    if esp_sid:
        socketio.emit("cmd", data, room=esp_sid)


@socketio.on("telemetry")
def handle_telemetry(data):
    global esp_last_seen
    if request.sid == esp_sid:
        esp_last_seen = time.time()
        socketio.emit("telemetry", data)


if __name__ == "__main__":
    socketio.run(app)
