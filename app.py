import os
from functools import wraps

import psycopg2
import psycopg2.extras
from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

DATABASE_URL = os.environ["DATABASE_URL"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


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
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
            """
        )
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
        cur.execute(
            "ALTER TABLE todo ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users (id)"
        )
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        error = None
        if not username or not password:
            error = "아이디와 비밀번호를 모두 입력하세요."

        if error is None:
            db = get_db()
            try:
                with db, db.cursor() as cur:
                    cur.execute(
                        "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                        (username, generate_password_hash(password)),
                    )
            except psycopg2.errors.UniqueViolation:
                db.rollback()
                error = "이미 존재하는 아이디입니다."
            else:
                return redirect(url_for("login"))
        return render_template("register.html", error=error)

    return render_template("register.html", error=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE username = %s", (username,))
            user = cur.fetchone()

        error = None
        if user is None or not check_password_hash(user["password_hash"], password):
            error = "아이디 또는 비밀번호가 올바르지 않습니다."

        if error is None:
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("index"))
        return render_template("login.html", error=error)

    return render_template("login.html", error=None)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    db = get_db()
    with db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT * FROM todo WHERE user_id = %s ORDER BY done ASC, id DESC",
            (session["user_id"],),
        )
        todos = cur.fetchall()
    return render_template("index.html", todos=todos, username=session["username"])


@app.route("/add", methods=["POST"])
@login_required
def add():
    content = request.form.get("content", "").strip()
    if content:
        db = get_db()
        with db, db.cursor() as cur:
            cur.execute(
                "INSERT INTO todo (user_id, content) VALUES (%s, %s)",
                (session["user_id"], content),
            )
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    db = get_db()
    with db, db.cursor() as cur:
        cur.execute(
            "UPDATE todo SET done = NOT done WHERE id = %s AND user_id = %s",
            (todo_id, session["user_id"]),
        )
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    db = get_db()
    with db, db.cursor() as cur:
        cur.execute(
            "DELETE FROM todo WHERE id = %s AND user_id = %s",
            (todo_id, session["user_id"]),
        )
    return redirect(url_for("index"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
