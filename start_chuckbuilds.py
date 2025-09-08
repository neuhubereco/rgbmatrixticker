#!/usr/bin/env python3
"""Vereinfachter Start für RGB Matrix Ticker mit ChuckBuilds."""

import os
import sys
import json
import shutil
from pathlib import Path

def setup_environment():
    """Umgebung für ChuckBuilds vorbereiten."""
    print("Bereite ChuckBuilds-Umgebung vor...")
    
    # Konfiguration kopieren
    config_src = "config/config_simple.json"
    config_dst = "config/config.json"
    
    if os.path.exists(config_src):
        shutil.copy2(config_src, config_dst)
        print(f"Konfiguration kopiert: {config_src} -> {config_dst}")
    else:
        print(f"Warnung: {config_src} nicht gefunden")
    
    # Assets-Verzeichnis erstellen falls nicht vorhanden
    assets_dir = Path("assets")
    if not assets_dir.exists():
        assets_dir.mkdir(parents=True)
        print("Assets-Verzeichnis erstellt")
    
    # Fonts-Verzeichnis erstellen
    fonts_dir = assets_dir / "fonts"
    if not fonts_dir.exists():
        fonts_dir.mkdir(parents=True)
        print("Fonts-Verzeichnis erstellt")
    
    print("Umgebung vorbereitet!")

def main():
    """Hauptfunktion."""
    print("RGB Matrix Ticker mit ChuckBuilds System")
    print("=" * 50)
    
    # Umgebung vorbereiten
    setup_environment()
    
    # ChuckBuilds Display Controller starten
    print("\nStarte ChuckBuilds Display Controller...")
    try:
        from src.display_controller import DisplayController
        display_controller = DisplayController()
        print("✓ Display Controller erfolgreich gestartet")
        
        # Web-Interface starten
        print("\nStarte Web-Interface...")
        from app_chuckbuilds import app
        print("✓ Web-Interface bereit auf http://localhost:8000")
        print("\nVerfügbare Endpunkte:")
        print("  GET  /status     - System-Status")
        print("  GET  /tickers    - Aktuelle Ticker anzeigen")
        print("  POST /tickers    - Ticker hinzufügen")
        print("  DEL  /tickers/X  - Ticker entfernen")
        print("  GET  /news       - News-Feed anzeigen")
        print("  POST /news       - News-Feed setzen")
        print("\nBeispiel-Ticker hinzufügen:")
        print("  curl -X POST http://localhost:8000/tickers -H 'Content-Type: application/json' -d '{\"symbol\":\"AAPL\",\"type\":\"stock\"}'")
        print("  curl -X POST http://localhost:8000/tickers -H 'Content-Type: application/json' -d '{\"symbol\":\"BTC-USD\",\"type\":\"crypto\"}'")
        print("\nDrücken Sie Ctrl+C zum Beenden")
        
        app.run(host="0.0.0.0", port=8000, debug=False)
        
    except KeyboardInterrupt:
        print("\n\nBeendet durch Benutzer")
    except Exception as e:
        print(f"\nFehler: {e}")
        print("Stelle sicher, dass alle Abhängigkeiten installiert sind:")
        print("  pip install -r requirements_chuckbuilds.txt")
        sys.exit(1)

if __name__ == "__main__":
    main()
