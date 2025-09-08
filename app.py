"""Web interface and display loop for the RGB matrix ticker."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from auth import Auth, login_required
from matrix_display import MatrixDisplay
from news import NewsFetcher
from ticker_manager import TickerManager

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = "change-me"
manager = TickerManager()
news_fetcher = NewsFetcher()
display = MatrixDisplay()
auth = Auth()


# ---------------------------------------------------------------------------
# Background display loop

def display_loop() -> None:
    while True:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        display.show_message(now)
        time.sleep(2)

        ticker_str = manager.build_ticker_string()
        if ticker_str:
            display.show_message(ticker_str)
            time.sleep(2)

        headlines = news_fetcher.headline_string()
        if headlines:
            display.show_message(headlines)
            time.sleep(2)


threading.Thread(target=display_loop, daemon=True).start()


# ---------------------------------------------------------------------------
# Web interface and API


@app.route("/login", methods=["GET", "POST"])
def login() -> str:
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
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index() -> str:
    return render_template(
        "index.html",
        tickers=manager.as_dict(),
        feed_url=news_fetcher.feed_url,
        brightness=display.brightness,
    )


@app.route("/add_ticker", methods=["POST"])
@login_required
def add_ticker() -> str:
    symbol = request.form.get("symbol")
    kind = request.form.get("type", "stock")
    if symbol:
        manager.add_ticker(symbol, kind)
    return redirect(url_for("index"))


@app.route("/remove_ticker")
@login_required
def remove_ticker() -> str:
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
    current = request.form.get("current_password")
    new_pw = request.form.get("new_password")
    user = session.get("user", "")
    if current and new_pw and auth.verify(user, current):
        auth.set_password(user, new_pw)
    return redirect(url_for("index"))


# JSON API endpoints (require login)


@app.route("/tickers", methods=["GET", "POST"])
@login_required
def tickers() -> str:
    if request.method == "POST":
        data = request.get_json(force=True)
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
        data = request.get_json(force=True)
        feed = data.get("feed_url")
        if feed:
            news_fetcher.set_feed(feed)
    return jsonify({"feed_url": news_fetcher.feed_url})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

