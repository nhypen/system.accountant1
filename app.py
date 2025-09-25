from __future__ import annotations
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
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
    with get_db() as db:
        db.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         TEXT NOT NULL DEFAULT (datetime('now')),
            kind       TEXT NOT NULL CHECK (kind IN ('buy','sell','balance')),
            product    TEXT,                -- dla buy/sell
            unit_price REAL,               -- dla buy/sell
            qty        INTEGER,            -- dla buy/sell
            comment    TEXT,               -- dla balance
            value      REAL                -- dla balance (może być ujemne)
        );
        """)
        db.commit()


# --- domain helpers ---
def calc_state(db: sqlite3.Connection) -> Tuple[Dict[str, int], float]:
    """
    Zwraca (magazyn: {produkt: ilość}, saldo_gotówki: float).
    Zasady:
      - buy  -> powiększa magazyn, ZMNIEJSZA saldo o unit_price*qty
      - sell -> zmniejsza magazyn, ZWIĘKSZA saldo o unit_price*qty
      - balance -> koryguje saldo o 'value' (może dodać/odjąć)
    """
    stock: Dict[str, int] = {}
    cash: float = 0.0

    for row in db.execute("SELECT * FROM entries ORDER BY id ASC"):
        kind = row["kind"]
        if kind == "buy":
            product = row["product"]
            qty = row["qty"] or 0
            price = row["unit_price"] or 0.0
            stock[product] = stock.get(product, 0) + qty
            cash -= price * qty
        elif kind == "sell":
            product = row["product"]
            qty = row["qty"] or 0
            price = row["unit_price"] or 0.0
            stock[product] = stock.get(product, 0) - qty
            cash += price * qty
        elif kind == "balance":
            cash += float(row["value"] or 0.0)

    # usuń produkty z ilością 0, żeby lista była czytelniejsza
    stock = {k: v for k, v in stock.items() if v != 0}
    return stock, round(cash, 2)


# --- routes ---
@app.route("/", methods=["GET"])
def index():
    with get_db() as db:
        stock, cash = calc_state(db)
    return render_template("index.html", stock=stock, cash=cash)


@app.post("/buy")
def buy():
    product = (request.form.get("product") or "").strip()
    unit_price = request.form.get("unit_price")
    qty = request.form.get("qty")

    if not product or not unit_price or not qty:
        flash("Uzupełnij: nazwa, cena, liczba sztuk.", "error")
        return redirect(url_for("index"))

    try:
        price = float(unit_price)
        q = int(qty)
        if q <= 0 or price < 0:
            raise ValueError()
    except ValueError:
        flash("Cena musi być liczbą, ilość dodatnia.", "error")
        return redirect(url_for("index"))

    with get_db() as db:
        db.execute(
            "INSERT INTO entries (kind, product, unit_price, qty) VALUES (?,?,?,?)",
            ("buy", product, price, q),
        )
        db.commit()
    flash("Zakup zapisany.", "ok")
    return redirect(url_for("index"))


@app.post("/sell")
def sell():
    product = (request.form.get("product") or "").strip()
    unit_price = request.form.get("unit_price")
    qty = request.form.get("qty")

    if not product or not unit_price or not qty:
        flash("Uzupełnij: nazwa, cena, liczba sztuk.", "error")
        return redirect(url_for("index"))

    try:
        price = float(unit_price)
        q = int(qty)
        if q <= 0 or price < 0:
            raise ValueError()
    except ValueError:
        flash("Cena musi być liczbą, ilość dodatnia.", "error")
        return redirect(url_for("index"))

    with get_db() as db:
        db.execute(
            "INSERT INTO entries (kind, product, unit_price, qty) VALUES (?,?,?,?)",
            ("sell", product, price, q),
        )
        db.commit()
    flash("Sprzedaż zapisana.", "ok")
    return redirect(url_for("index"))


@app.post("/balance")
def balance():
    comment = (request.form.get("comment") or "").strip()
    value = request.form.get("value")
    if not value:
        flash("Podaj wartość (liczbowa).", "error")
        return redirect(url_for("index"))
    try:
        val = float(value)
    except ValueError:
        flash("Wartość musi być liczbą.", "error")
        return redirect(url_for("index"))

    with get_db() as db:
        db.execute(
            "INSERT INTO entries (kind, comment, value) VALUES (?,?,?)",
            ("balance", comment, val),
        )
        db.commit()
    flash("Zmiana salda zapisana.", "ok")
    return redirect(url_for("index"))


@app.get("/history/")
@app.get("/history/<int:line_from>/<int:line_to>/")
def history(line_from: Optional[int] = None, line_to: Optional[int] = None):
    with get_db() as db:
        if line_from is None or line_to is None:
            rows = db.execute("SELECT * FROM entries ORDER BY id DESC").fetchall()
            scope = None
        else:
            if line_from > line_to:
                line_from, line_to = line_to, line_from
            rows = db.execute(
                "SELECT * FROM entries WHERE id BETWEEN ? AND ? ORDER BY id DESC",
                (line_from, line_to),
            ).fetchall()
            scope = (line_from, line_to)
        stock, cash = calc_state(db)

    return render_template("history.html", rows=rows, scope=scope, stock=stock, cash=cash)

# --- run ---
if __name__ == "__main__":
    init_db()
    app.run(debug=True)
