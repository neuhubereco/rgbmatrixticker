# RGB Matrix Ticker mit ChuckBuilds System

Dieses Projekt wurde umgebaut, um das [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) System als Basis zu verwenden. Es bietet eine moderne, erweiterte Display-Engine mit verbesserter Hardware-Unterstützung.

## Features

- **Moderne Display-Engine**: Verwendet das ChuckBuilds-System für bessere Hardware-Kompatibilität
- **Aktien & Krypto-Ticker**: Echtzeitdaten für Aktien und Kryptowährungen
- **RSS-News**: Konfigurierbare News-Feeds
- **Web-Interface**: REST-API für einfache Konfiguration
- **Hardware-Fallback**: Funktioniert auch ohne echte LED-Matrix (Konsolen-Ausgabe)

## Installation

1. **Abhängigkeiten installieren:**
   ```bash
   pip install -r requirements_chuckbuilds.txt
   ```

2. **System starten:**
   ```bash
   python start_chuckbuilds.py
   ```

## Verwendung

### Web-Interface

Das System startet einen Web-Server auf `http://localhost:8000` mit folgenden Endpunkten:

#### Ticker verwalten

**Aktuelle Ticker anzeigen:**
```bash
curl http://localhost:8000/tickers
```

**Aktie hinzufügen:**
```bash
curl -X POST http://localhost:8000/tickers \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","type":"stock"}'
```

**Kryptowährung hinzufügen:**
```bash
curl -X POST http://localhost:8000/tickers \
  -H "Content-Type: application/json" \
  -d '{"symbol":"BTC-USD","type":"crypto"}'
```

**Ticker entfernen:**
```bash
curl -X DELETE http://localhost:8000/tickers/AAPL
```

#### News-Feed verwalten

**News-Feed setzen:**
```bash
curl -X POST http://localhost:8000/news \
  -H "Content-Type: application/json" \
  -d '{"feed_url":"https://news.google.com/rss"}'
```

**Aktuellen Feed anzeigen:**
```bash
curl http://localhost:8000/news
```

#### System-Status

```bash
curl http://localhost:8000/status
```

## Konfiguration

Die Hauptkonfiguration befindet sich in `config/config.json`. Wichtige Einstellungen:

### Display-Hardware
```json
{
  "display": {
    "hardware": {
      "rows": 32,
      "cols": 64,
      "chain_length": 2,
      "parallel": 1,
      "brightness": 95,
      "hardware_mapping": "adafruit-hat-pwm"
    }
  }
}
```

### Ticker-Einstellungen
```json
{
  "stocks": {
    "enabled": true,
    "update_interval": 600,
    "symbols": ["AAPL", "GOOGL", "MSFT"]
  },
  "crypto": {
    "enabled": true,
    "update_interval": 600,
    "symbols": ["BTC-USD", "ETH-USD"]
  }
}
```

## Hardware-Unterstützung

Das System unterstützt verschiedene RGB-Matrix-Konfigurationen:

- **64x32 Panels**: Standard-Konfiguration
- **Chain-Length**: Mehrere Panels hintereinander
- **Hardware-Mapping**: Verschiedene HAT-Konfigurationen
- **Fallback-Modus**: Konsolen-Ausgabe ohne Hardware

## Unterschiede zum Original

### Vorteile des ChuckBuilds-Systems:
- **Bessere Hardware-Kompatibilität**: Unterstützt mehr RGB-Matrix-Typen
- **Erweiterte Konfiguration**: Detaillierte Hardware-Einstellungen
- **Moderne Architektur**: Modularer Aufbau mit Manager-Pattern
- **Caching-System**: Reduziert API-Aufrufe
- **Web-Interface v2**: Modernere Benutzeroberfläche

### Vereinfachte Features:
- Fokus auf Ticker und News (keine Sport-Scores, Wetter, etc.)
- Vereinfachte API-Endpunkte
- Deutsche Lokalisierung

## Entwicklung

### Projektstruktur
```
rgbmatrixticker/
├── src/                    # ChuckBuilds Source-Code
├── config/                 # Konfigurationsdateien
├── assets/                 # Fonts und Assets
├── app_chuckbuilds.py      # Hauptanwendung
├── start_chuckbuilds.py    # Startskript
└── requirements_chuckbuilds.txt
```

### Debugging

Für Debugging ohne Hardware:
```bash
# Fallback-Modus aktivieren
export LEDMATRIX_FALLBACK=1
python start_chuckbuilds.py
```

## Lizenz

Basierend auf dem [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) Projekt.
