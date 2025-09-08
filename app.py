"""Web interface and display loop for the RGB matrix ticker."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime

from flask import Flask, jsonify, request

from matrix_display import MatrixDisplay
from news import NewsFetcher
from ticker_manager import TickerManager

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
manager = TickerManager()
news_fetcher = NewsFetcher()
display = MatrixDisplay()


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
# HTTP API

@app.route("/tickers", methods=["GET", "POST"])
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
def delete_ticker(symbol: str) -> str:
    manager.remove_ticker(symbol)
    return jsonify({"status": "ok"})


@app.route("/news", methods=["GET", "POST"])
def news() -> str:
    if request.method == "POST":
        data = request.get_json(force=True)
        feed = data.get("feed_url")
        if feed:
            news_fetcher.set_feed(feed)
    return jsonify({"feed_url": news_fetcher.feed_url})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)

