from websockets.asyncio.server import serve


app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

