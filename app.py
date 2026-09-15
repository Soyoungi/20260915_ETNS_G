import os

import psycopg2
import psycopg2.extras
from flask import Flask, g, redirect, render_template, request, url_for

DATABASE_URL = os.environ["DATABASE_URL"]

app = Flask(__name__)


def get_db():
    if "db" not in g:
        g.db = psycopg2.connect(DATABASE_URL)
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    conn = psycopg2.connect(DATABASE_URL)
    with conn, conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS todo (
                id SERIAL PRIMARY KEY,
                content TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
    conn.close()


@app.route("/")
def index():
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("SELECT * FROM todo ORDER BY done ASC, id DESC")
        todos = cur.fetchall()
    return render_template("index.html", todos=todos)


@app.route("/add", methods=["POST"])
def add():
    content = request.form.get("content", "").strip()
    if content:
        db = get_db()
        with db, db.cursor() as cur:
            cur.execute("INSERT INTO todo (content) VALUES (%s)", (content,))
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
def toggle(todo_id):
    db = get_db()
    with db, db.cursor() as cur:
        cur.execute(
            "UPDATE todo SET done = NOT done WHERE id = %s", (todo_id,)
        )
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
def delete(todo_id):
    db = get_db()
    with db, db.cursor() as cur:
        cur.execute("DELETE FROM todo WHERE id = %s", (todo_id,))
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
