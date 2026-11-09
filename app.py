import os
import socket

import psycopg
from flask import Flask, jsonify

app = Flask(__name__)

# Message affiché sur la page d'accueil : à modifier pendant le workshop
MESSAGE = "Bonjour Alexy depuis mon pipeline !"
# Version injectée au build (SHA du commit en CI, "dev" par défaut)
VERSION = os.getenv("APP_VERSION", "dev")


@app.route("/")
def index():
    return (
        f"<h1>{MESSAGE}</h1>"
        f"<p>Version : <code>{VERSION[:7]}</code></p>"
        f"<p>Conteneur : <code>{socket.gethostname()}</code></p>"
    )


@app.route("/health")
def health():
    return jsonify(status="ok", version=VERSION)


@app.route("/db")
def db():
    try:
        with psycopg.connect(
            host=os.environ["DB_HOST"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            sslmode="require",
            connect_timeout=5,
        ) as conn:
            base, version = conn.execute(
                "SELECT current_database(), version()"
            ).fetchone()
    except (KeyError, psycopg.Error):
        # Le détail reste dans les journaux, jamais dans la réponse publique
        app.logger.exception("Connexion à PostgreSQL impossible")
        return jsonify(status="error"), 503
    return jsonify(status="ok", database=base, server=version)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
