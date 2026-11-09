import os
import socket

import psycopg
from flask import Flask, jsonify, render_template, request
from psycopg.rows import dict_row

app = Flask(__name__)

# Message affiché sur la page d'accueil : à modifier pendant le workshop
MESSAGE = "Bonjour Alexy depuis mon pipeline !"
# Version injectée au build (SHA du commit en CI, "dev" par défaut)
VERSION = os.getenv("APP_VERSION", "dev")

CATEGORIES = ("Docker", "Azure", "GitHub", "PostgreSQL")
TITRE_MAX = 120
# Le site est public et sans compte : on borne ce qui peut être écrit en base
LIGNES_MAX = 200

SQL_CREATION = """
    CREATE TABLE IF NOT EXISTS elements (
        id        SERIAL PRIMARY KEY,
        titre     TEXT NOT NULL,
        categorie TEXT NOT NULL,
        fait      BOOLEAN NOT NULL DEFAULT FALSE,
        cree_le   TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
"""
SQL_LECTURE = """SELECT id, titre, categorie, fait, cree_le
FROM elements
WHERE (categorie = %(categorie)s OR %(categorie)s IS NULL)
  AND (fait = %(fait)s OR %(fait)s IS NULL)
  AND (titre ILIKE %(motif)s OR %(motif)s IS NULL)
ORDER BY id DESC"""
SQL_AJOUT = "INSERT INTO elements (titre, categorie) VALUES (%s, %s) RETURNING id"
SQL_STATUT = "UPDATE elements SET fait = %s WHERE id = ANY(%s)"
SQL_SUPPRESSION = "DELETE FROM elements WHERE id = ANY(%s)"

table_prete = False


class RequeteInvalide(Exception):
    def __init__(self, message, code=400):
        super().__init__(message)
        self.message = message
        self.code = code


def connexion():
    try:
        return psycopg.connect(
            host=os.environ["DB_HOST"],
            dbname=os.environ["DB_NAME"],
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            sslmode="require",
            connect_timeout=5,
            row_factory=dict_row,
        )
    except KeyError as absente:
        raise psycopg.OperationalError(f"Variable absente : {absente}") from absente


def connexion_table():
    """Ouvre une connexion et crée la table à la première utilisation."""
    global table_prete
    conn = connexion()
    if not table_prete:
        conn.execute(SQL_CREATION)
        conn.commit()
        table_prete = True
    return conn


def lire_json():
    corps = request.get_json(silent=True)
    if not isinstance(corps, dict):
        raise RequeteInvalide("Requête illisible.")
    return corps


def lire_ids(corps):
    ids = corps.get("ids")
    valides = (
        isinstance(ids, list)
        and 0 < len(ids) <= LIGNES_MAX
        and all(type(i) is int and 0 < i < 2**31 for i in ids)
    )
    if not valides:
        raise RequeteInvalide("Sélection invalide.")
    return ids


@app.errorhandler(RequeteInvalide)
def requete_invalide(erreur):
    return jsonify(status="error", message=erreur.message), erreur.code


@app.errorhandler(psycopg.Error)
def base_indisponible(_erreur):
    # Le détail reste dans les journaux, jamais dans la réponse publique
    app.logger.exception("Connexion à PostgreSQL impossible")
    return jsonify(status="error", message="Base de données indisponible."), 503


@app.route("/")
def index():
    return render_template(
        "index.html",
        message=MESSAGE,
        version=VERSION[:7],
        conteneur=socket.gethostname(),
        categories=CATEGORIES,
        titre_max=TITRE_MAX,
    )


@app.route("/health")
def health():
    return jsonify(status="ok", version=VERSION)


@app.route("/db")
def db():
    with connexion() as conn:
        ligne = conn.execute(
            "SELECT current_database() AS base, version() AS serveur"
        ).fetchone()
    return jsonify(status="ok", database=ligne["base"], server=ligne["serveur"])


@app.get("/api/elements")
def lister():
    statuts = {"a_faire": False, "fait": True}
    categorie = request.args.get("categorie") or None
    recherche = request.args.get("q", "").strip()[:TITRE_MAX]
    filtres = {
        "categorie": categorie,
        "fait": statuts.get(request.args.get("statut")),
        "motif": f"%{recherche}%" if recherche else None,
    }
    with connexion_table() as conn:
        lignes = conn.execute(SQL_LECTURE, filtres).fetchall()
        infos = conn.execute(
            """SELECT current_database() AS base,
                      current_setting('server_version') AS version,
                      NOW() AS heure,
                      (SELECT COUNT(*) FROM elements) AS total"""
        ).fetchone()
    return jsonify(
        status="ok",
        elements=[
            {**ligne, "cree_le": ligne["cree_le"].isoformat()} for ligne in lignes
        ],
        base=infos["base"],
        version=infos["version"],
        heure=infos["heure"].isoformat(),
        total=infos["total"],
        total_max=LIGNES_MAX,
        sql=SQL_LECTURE,
    )


@app.post("/api/elements")
def ajouter():
    corps = lire_json()
    titre = corps.get("titre")
    categorie = corps.get("categorie")
    if not isinstance(titre, str) or not titre.strip():
        raise RequeteInvalide("Saisis un titre.")
    titre = titre.strip()
    if len(titre) > TITRE_MAX:
        raise RequeteInvalide(f"Le titre dépasse {TITRE_MAX} caractères.")
    if categorie not in CATEGORIES:
        raise RequeteInvalide("Choisis une catégorie de la liste.")
    with connexion_table() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM elements").fetchone()["n"]
        if total >= LIGNES_MAX:
            raise RequeteInvalide(
                f"La table est pleine ({LIGNES_MAX} lignes) : supprime des éléments.",
                409,
            )
        nouveau = conn.execute(SQL_AJOUT, (titre, categorie)).fetchone()["id"]
    return jsonify(status="ok", id=nouveau, sql=SQL_AJOUT), 201


@app.patch("/api/elements")
def changer_statut():
    corps = lire_json()
    ids = lire_ids(corps)
    fait = corps.get("fait")
    if not isinstance(fait, bool):
        raise RequeteInvalide("Statut invalide.")
    with connexion_table() as conn:
        modifiees = conn.execute(SQL_STATUT, (fait, ids)).rowcount
    return jsonify(status="ok", lignes=modifiees, sql=SQL_STATUT)


@app.delete("/api/elements")
def supprimer():
    ids = lire_ids(lire_json())
    with connexion_table() as conn:
        supprimees = conn.execute(SQL_SUPPRESSION, (ids,)).rowcount
    return jsonify(status="ok", lignes=supprimees, sql=SQL_SUPPRESSION)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
