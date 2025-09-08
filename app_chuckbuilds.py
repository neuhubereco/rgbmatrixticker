"""RGB Matrix Ticker mit ChuckBuilds Display-System."""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from flask import Flask, jsonify, request

# ChuckBuilds Imports
from src.display_controller import DisplayController
from src.config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = Flask(__name__)

# ChuckBuilds Display Controller initialisieren
display_controller = None

def initialize_display():
    """Display Controller initialisieren."""
    global display_controller
    try:
        display_controller = DisplayController()
        LOGGER.info("ChuckBuilds Display Controller erfolgreich initialisiert")
    except Exception as e:
        LOGGER.error(f"Fehler beim Initialisieren des Display Controllers: {e}")
        display_controller = None

# Display Controller im Hintergrund initialisieren
threading.Thread(target=initialize_display, daemon=True).start()

# ---------------------------------------------------------------------------
# HTTP API - Vereinfachte Version für Ticker und News

@app.route("/tickers", methods=["GET", "POST"])
def tickers() -> str:
    """Ticker verwalten."""
    if not display_controller:
        return jsonify({"error": "Display Controller nicht verfügbar"}), 503
    
    if request.method == "POST":
        data = request.get_json(force=True)
        symbol = data.get("symbol")
        kind = data.get("type", "stock")
        
        if not symbol:
            return jsonify({"error": "Symbol fehlt"}), 400
        
        # ChuckBuilds Stock Manager verwenden
        if hasattr(display_controller, 'stocks') and display_controller.stocks:
            if kind == "crypto":
                # Für Krypto: Symbol zu crypto symbols hinzufügen
                crypto_config = display_controller.config.get('crypto', {})
                symbols = crypto_config.get('symbols', [])
                if symbol.upper() not in symbols:
                    symbols.append(symbol.upper())
                    crypto_config['symbols'] = symbols
                    crypto_config['enabled'] = True
                    display_controller.config['crypto'] = crypto_config
            else:
                # Für Aktien: Symbol zu stock symbols hinzufügen
                stocks_config = display_controller.config.get('stocks', {})
                symbols = stocks_config.get('symbols', [])
                if symbol.upper() not in symbols:
                    symbols.append(symbol.upper())
                    stocks_config['symbols'] = symbols
                    stocks_config['enabled'] = True
                    display_controller.config['stocks'] = stocks_config
        
        return jsonify({"status": "ok", "symbol": symbol, "type": kind})
    
    # GET: Aktuelle Ticker zurückgeben
    result = {"stocks": [], "crypto": []}
    if display_controller:
        stocks_config = display_controller.config.get('stocks', {})
        crypto_config = display_controller.config.get('crypto', {})
        result["stocks"] = stocks_config.get('symbols', [])
        result["crypto"] = crypto_config.get('symbols', [])
    
    return jsonify(result)

@app.route("/tickers/<symbol>", methods=["DELETE"])
def delete_ticker(symbol: str) -> str:
    """Ticker entfernen."""
    if not display_controller:
        return jsonify({"error": "Display Controller nicht verfügbar"}), 503
    
    symbol = symbol.upper()
    
    # Aus stocks entfernen
    stocks_config = display_controller.config.get('stocks', {})
    symbols = stocks_config.get('symbols', [])
    if symbol in symbols:
        symbols.remove(symbol)
        stocks_config['symbols'] = symbols
        display_controller.config['stocks'] = stocks_config
    
    # Aus crypto entfernen
    crypto_config = display_controller.config.get('crypto', {})
    symbols = crypto_config.get('symbols', [])
    if symbol in symbols:
        symbols.remove(symbol)
        crypto_config['symbols'] = symbols
        display_controller.config['crypto'] = crypto_config
    
    return jsonify({"status": "ok", "removed": symbol})

@app.route("/news", methods=["GET", "POST"])
def news() -> str:
    """News-Feed verwalten."""
    if not display_controller:
        return jsonify({"error": "Display Controller nicht verfügbar"}), 503
    
    if request.method == "POST":
        data = request.get_json(force=True)
        feed_url = data.get("feed_url")
        
        if feed_url:
            # ChuckBuilds News Manager konfigurieren
            news_config = display_controller.config.get('news_manager', {})
            news_config['enabled'] = True
            news_config['custom_feeds'] = {"Custom": feed_url}
            news_config['enabled_feeds'] = ["Custom"]
            display_controller.config['news_manager'] = news_config
            
            return jsonify({"status": "ok", "feed_url": feed_url})
    
    # GET: Aktuellen Feed zurückgeben
    news_config = display_controller.config.get('news_manager', {})
    custom_feeds = news_config.get('custom_feeds', {})
    feed_url = list(custom_feeds.values())[0] if custom_feeds else None
    
    return jsonify({"feed_url": feed_url})

@app.route("/status", methods=["GET"])
def status() -> str:
    """System-Status abfragen."""
    if not display_controller:
        return jsonify({"status": "error", "message": "Display Controller nicht verfügbar"})
    
    return jsonify({
        "status": "ok",
        "display_controller": "aktiv",
        "config_loaded": bool(display_controller.config)
    })

if __name__ == "__main__":
    LOGGER.info("Starte RGB Matrix Ticker mit ChuckBuilds System...")
    app.run(host="0.0.0.0", port=8000, debug=True)
