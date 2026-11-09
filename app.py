import os
import socket

from flask import Flask, jsonify

MESSAGE = "Bonjour depuis le workshop CI/CD !"
VERSION = os.environ.get("APP_VERSION", "dev")

app = Flask(__name__)


@app.get("/")
def index():
    return (
        "<h1>{}</h1>"
        "<p>Version : <strong>{}</strong></p>"
        "<p>Conteneur : <code>{}</code></p>"
    ).format(MESSAGE, VERSION, socket.gethostname())


@app.get("/health")
def health():
    return jsonify(status="ok", version=VERSION)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
