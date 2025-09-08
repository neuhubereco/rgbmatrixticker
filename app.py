"""Web interface and display loop for the RGB matrix ticker."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from matrix_display import MatrixDisplay
from news import NewsFetcher
from ticker_manager import TickerManager

# -----------------------------------------------------------------------------
# Optionales Auth – wenn kein auth.py vorhanden ist, wird ohne Login gearbeitet.
try:
    from auth import Auth, login_required  # type: ignore
    _AUTH_AVAILABLE = True
except Exception:  # auth.py nicht vorhanden oder fehlerhaft
    _AUTH_AVAILABLE = False

    def login_required(fn):  # No-Op Decorator
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        wrapper.__name__ = fn.__name__
        return wrapper

    class Auth:  # Platzhalter
        def verify(self, *_args, **_kwargs) -> bool: return True
        def set_password(self, *_args, **_kwargs) -> None: pass
# -----------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "change-me"  # setze hier einen sicheren Secret-Key

manager = TickerManager()
news_fetcher = NewsFetcher()
display = MatrixDisplay()
auth = Auth()

# -----------------------------------------------------------------------------
# Hintergrund-Display-Loop
def display_loop() -> None:
    while True:
        # 1) Datum/Uhrzeit
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display.show_message(now)
        time.sleep(2)

        # 2) Ticker (Stocks/Krypto/etc.)
        ticker_str = manager.build_ticker_string()
        if ticker_str:
            display.show_message(ticker_str)
            time.sleep(2)

        # 3) News-Headlines
        headlines = news_fetcher.headline_string()
        if headlines:
            display.show_message(headlines)
            time.sleep(2)

threading.Thread(target=display_loop, daemon=True).start()

# -----------------------------------------------------------------------------
# Web-UI (nur sichtbar sinnvoll, wenn Templates vorhanden sind)
@app.route("/login", methods=["GET", "POST"])
def login() -> str:
    if not _AUTH_AVAILABLE:
        return redirect(url_for("index"))
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if auth.verify(username, password):
            session["user"] = username
            return redirect(url_for("index"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/logout")
def logout() -> str:
    session.clear()
    return redirect(url_for("login" if _AUTH_AVAILABLE else "index"))

@app.route("/")
@login_required
def index() -> str:
    # Wenn keine Templates da sind, gib eine einfache JSON-Ansicht zurück
    try:
        return render_template(
            "index.html",
            tickers=manager.as_dict(),
            feed_url=news_fetcher.feed_url,
            brightness=display.brightness,
        )
    except Exception:
        return jsonify({
            "tickers": manager.as_dict(),
            "feed_url": news_fetcher.feed_url,
            "brightness": display.brightness,
            "auth": _AUTH_AVAILABLE,
        })

@app.route("/add_ticker", methods=["POST"])
@login_required
def add_ticker_form() -> str:
    symbol = request.form.get("symbol")
    kind = request.form.get("type", "stock")
    if symbol:
        manager.add_ticker(symbol, kind)
    return redirect(url_for("index"))

@app.route("/remove_ticker")
@login_required
def remove_ticker_form() -> str:
    symbol = request.args.get("symbol")
    if symbol:
        manager.remove_ticker(symbol)
    return redirect(url_for("index"))

@app.route("/set_news", methods=["POST"])
@login_required
def set_news() -> str:
    feed = request.form.get("feed_url")
    if feed:
        news_fetcher.set_feed(feed)
    return redirect(url_for("index"))

@app.route("/brightness", methods=["POST"])
@login_required
def brightness() -> str:
    try:
        value = int(request.form.get("value", "100"))
    except ValueError:
        value = 100
    display.set_brightness(value)
    return redirect(url_for("index"))

@app.route("/change_password", methods=["POST"])
@login_required
def change_password() -> str:
    if not _AUTH_AVAILABLE:
        return redirect(url_for("index"))
    current = request.form.get("current_password")
    new_pw = request.form.get("new_password")
    user = session.get("user", "")
    if current and new_pw and auth.verify(user, current):
        auth.set_password(user, new_pw)
    return redirect(url_for("index"))

# -----------------------------------------------------------------------------
# JSON-API
@app.route("/tickers", methods=["GET", "POST"])
@login_required
def tickers() -> str:
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        symbol = data.get("symbol")
        kind = data.get("type", "stock")
        if not symbol:
            return jsonify({"error": "missing symbol"}), 400
        manager.add_ticker(symbol, kind)
    return jsonify(manager.as_dict())

@app.route("/tickers/<symbol>", methods=["DELETE"])
@login_required
def delete_ticker(symbol: str) -> str:
    manager.remove_ticker(symbol)
    return jsonify({"status": "ok"})

@app.route("/news", methods=["GET", "POST"])
@login_required
def news() -> str:
    if request.method == "POST":
        data = request.get_json(force=True) or {}
        feed = data.get("feed_url")
        if feed:
            news_fetcher.set_feed(feed)
    return jsonify({"feed_url": news_fetcher.feed_url})

# -----------------------------------------------------------------------------
if __name__ == "__main__":
    # Flask-Dev-Server; für Produktion lieber gunicorn/systemd nutzen
    app.run(host="0.0.0.0", port=8000)
