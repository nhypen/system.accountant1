from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from flask import Flask, render_template, request, redirect, url_for, flash

# --- DB & Flask setup ---
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "app.db"

app = Flask(__name__)
app.secret_key = "dev-secret-change-me"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Utwórz tabelę zdarzeń, jeśli nie istnieje."""
    with get_db() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
              id         INTEGER PRIMARY KEY AUTOINCREMENT,
              ts         TEXT    NOT NULL,
              kind       TEXT    NOT NULL CHECK(kind IN ('buy','sell','balance')),
              product    TEXT,
              unit_price REAL,
              qty        INTEGER,
              comment    TEXT,
              value      REAL
            );
            """
        )


# --- obliczenia stanu magazynu i salda ---
def calc_state(db: sqlite3.Connection) -> Tuple[Dict[str, int], float]:
    stock: Dict[str, int] = {}
    cash: float = 0.0

    rows = db.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
    for r in rows:
        kind = r["kind"]
        if kind == "buy":
            name = r["product"]
            qty = int(r["qty"] or 0)
            price = float(r["unit_price"] or 0.0)
            stock[name] = stock.get(name, 0) + qty
            cash -= price * qty
        elif kind == "sell":
            name = r["product"]
            qty = int(r["qty"] or 0)
            price = float(r["unit_price"] or 0.0)
            stock[name] = stock.get(name, 0) - qty
            cash += price * qty
        elif kind == "balance":
            cash += float(r["value"] or 0.0)

    # usuń produkty o stanie 0, żeby tabela była czytelna
    stock = {k: v for k, v in stock.items() if v != 0}
    return stock, cash


# --- ROUTES ---

@app.get("/")
def index():
    with get_db() as db:
        stock, cash = calc_state(db)
    return render_template("index.html", stock=stock, cash=cash)


@app.post("/add")
def add_event():
    """Jeden endpoint dla trzech formularzy – rozpoznajemy po hidden 'form_name'."""
    kind = request.form.get("form_name")

    now = datetime.utcnow().isoformat(timespec="seconds")
    with get_db() as db:
        if kind == "buy":
            name = request.form.get("buy_name", "").strip()
            price = float(request.form.get("buy_price", "0") or 0)
            qty = int(request.form.get("buy_qty", "0") or 0)
            if not name or qty <= 0:
                flash("Podaj nazwę produktu i dodatnią liczbę sztuk.", "error")
            else:
                db.execute(
                    "INSERT INTO events(ts,kind,product,unit_price,qty) VALUES(?,?,?,?,?)",
                    (now, "buy", name, price, qty),
                )
                flash("Zakup zapisany.", "ok")

        elif kind == "sell":
            name = request.form.get("sell_name", "").strip()
            price = float(request.form.get("sell_price", "0") or 0)
            qty = int(request.form.get("sell_qty", "0") or 0)
            if not name or qty <= 0:
                flash("Podaj nazwę produktu i dodatnią liczbę sztuk.", "error")
            else:
                db.execute(
                    "INSERT INTO events(ts,kind,product,unit_price,qty) VALUES(?,?,?,?,?)",
                    (now, "sell", name, price, qty),
                )
                flash("Sprzedaż zapisana.", "ok")

        elif kind == "balance":
            comment = request.form.get("bal_comment", "").strip()
            try:
                value = float(request.form.get("bal_value", "0"))
            except ValueError:
                value = None
            if value is None:
                flash("Wartość salda musi być liczbą.", "error")
            else:
                db.execute(
                    "INSERT INTO events(ts,kind,comment,value) VALUES(?,?,?,?)",
                    (now, "balance", comment, value),
                )
                flash("Zmiana salda zapisana.", "ok")

    return redirect(url_for("index"))


@app.get("/history/")
@app.get("/history/<int:line_from>/<int:line_to>/")
def history(line_from: Optional[int] = None, line_to: Optional[int] = None):
    with get_db() as db:
        if line_from is None or line_to is None:
            rows = db.execute("SELECT * FROM events ORDER BY id ASC").fetchall()
            scope = None
        else:
            rows = db.execute(
                "SELECT * FROM events WHERE id BETWEEN ? AND ? ORDER BY id ASC",
                (line_from, line_to),
            ).fetchall()
            scope = (line_from, line_to)

        stock, cash = calc_state(db)

    return render_template("history.html", rows=rows, cash=cash, stock=stock, scope=scope)

from flask import request, redirect, url_for, flash

@app.post("/buy")
def buy():
    # TODO: tu później dodamy zapis zakupu do bazy
    flash("Zakup zapisany (stub).")
    return redirect(url_for("index"))

@app.post("/sell")
def sell():
    # TODO: tu później dodamy zapis sprzedaży do bazy
    flash("Sprzedaż zapisana (stub).")
    return redirect(url_for("index"))

@app.post("/cash")
def cash():
    # TODO: tu później dodamy zmianę salda
    flash("Zmiana salda zapisana (stub).")
    return redirect(url_for("index"))

# --- run ---
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5002)

