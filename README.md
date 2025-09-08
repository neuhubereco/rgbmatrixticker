# RGB Matrix Ticker mit ChuckBuilds System

Ein moderner RGB-Matrix-Ticker, der das [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) System als Basis verwendet. Das Projekt wurde erfolgreich von der ursprünglichen `rgbmatrix`-Bibliothek auf das erweiterte ChuckBuilds-System umgestellt.

## ✨ Features

- **🚀 Moderne Display-Engine**: Verwendet das ChuckBuilds-System für bessere Hardware-Kompatibilität
- **📈 Aktien & Krypto-Ticker**: Echtzeitdaten für Aktien und Kryptowährungen
- **📰 RSS-News**: Konfigurierbare News-Feeds
- **🌐 Web-Interface**: REST-API für einfache Konfiguration
- **💻 Hardware-Fallback**: Funktioniert auch ohne echte LED-Matrix (Konsolen-Ausgabe)
- **⚙️ Erweiterte Konfiguration**: Detaillierte Hardware-Einstellungen
- **�� Caching-System**: Reduziert API-Aufrufe
- **🇩🇪 Deutsche Lokalisierung**: Alle Meldungen auf Deutsch

## 🚀 Schnellstart

### 1. Installation

```bash
# Repository klonen
git clone https://github.com/neuhubereco/rgbmatrixticker.git
cd rgbmatrixticker

# Abhängigkeiten installieren
pip3 install -r requirements_chuckbuilds.txt
```

### 2. System starten

```bash
# ChuckBuilds-Version starten (empfohlen)
python3 start_chuckbuilds.py

# Oder ursprüngliche Version
python3 app.py
```

### 3. Web-Interface verwenden

Das System startet einen Web-Server auf `http://localhost:8000`

**Status prüfen:**
```bash
curl http://localhost:8000/status
```

## 📖 Verwendung

### Ticker verwalten

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

### News-Feed verwalten

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

### System-Status

```bash
curl http://localhost:8000/status
```

**Erwartete Antwort:**
```json
{
  "status": "ok",
  "display_controller": "aktiv",
  "config_loaded": true
}
```

## ⚙️ Konfiguration

### ChuckBuilds-System (empfohlen)

Die Hauptkonfiguration befindet sich in `config/config.json`:

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
  },
  "stocks": {
    "enabled": true,
    "symbols": ["AAPL", "GOOGL", "MSFT"]
  },
  "crypto": {
    "enabled": true,
    "symbols": ["BTC-USD", "ETH-USD"]
  }
}
```

### Ursprüngliches System

Die ursprüngliche Version verwendet `app.py` mit einfacheren Einstellungen.

## 🔧 Hardware-Unterstützung

### ChuckBuilds-System
- **64x32 Panels**: Standard-Konfiguration
- **Chain-Length**: Mehrere Panels hintereinander
- **Hardware-Mapping**: Verschiedene HAT-Konfigurationen
- **Fallback-Modus**: Konsolen-Ausgabe ohne Hardware

### Ursprüngliches System
- **rgbmatrix-Bibliothek**: Direkte Hardware-Ansteuerung
- **Einfache Konfiguration**: Weniger Optionen

## 📁 Projektstruktur

```
rgbmatrixticker/
├── src/                           # ChuckBuilds Source-Code
│   ├── display_controller.py      # Haupt-Controller
│   ├── display_manager.py         # Display-Management
│   ├── rgbmatrix_fallback.py     # Fallback ohne Hardware
│   └── ...
├── config/                        # Konfigurationsdateien
│   ├── config.json               # ChuckBuilds-Konfiguration
│   └── config_simple.json        # Vereinfachte Konfiguration
├── assets/                        # Fonts und Assets
├── app.py                        # Ursprüngliche Hauptanwendung
├── app_chuckbuilds.py            # ChuckBuilds-Hauptanwendung
├── start_chuckbuilds.py          # ChuckBuilds-Startskript
├── requirements.txt              # Ursprüngliche Abhängigkeiten
├── requirements_chuckbuilds.txt  # ChuckBuilds-Abhängigkeiten
└── README.md                     # Diese Datei
```

## 🔄 Migration von rgbmatrix zu ChuckBuilds

Das Projekt wurde erfolgreich von der ursprünglichen `rgbmatrix`-Bibliothek auf das ChuckBuilds-System migriert:

### Vorteile der Migration:
- ✅ **Bessere Hardware-Kompatibilität**: Unterstützt mehr RGB-Matrix-Typen
- ✅ **Erweiterte Konfiguration**: Detaillierte Hardware-Einstellungen
- ✅ **Moderne Architektur**: Modularer Aufbau mit Manager-Pattern
- ✅ **Caching-System**: Reduziert API-Aufrufe
- ✅ **Fallback-Unterstützung**: Funktioniert ohne Hardware
- ✅ **Deutsche Lokalisierung**: Alle Meldungen auf Deutsch

### Beibehaltene Features:
- ✅ **Ticker-Management**: Aktien und Krypto-Symbole
- ✅ **News-Integration**: RSS-Feed-Unterstützung
- ✅ **Web-API**: REST-Endpunkte für Konfiguration
- ✅ **Hardware-Fallback**: Konsolen-Ausgabe ohne Matrix

## 🐛 Debugging

### Fallback-Modus aktivieren
```bash
# Für ChuckBuilds-System
export LEDMATRIX_FALLBACK=1
python3 start_chuckbuilds.py
```

### Logs anzeigen
```bash
# Detaillierte Logs
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
from src.display_controller import DisplayController
controller = DisplayController()
"
```

### System-Status prüfen
```bash
# Web-Interface Status
curl http://localhost:8000/status

# Ticker-Status
curl http://localhost:8000/tickers

# News-Status
curl http://localhost:8000/news
```

## 📋 API-Referenz

### GET /status
Gibt den System-Status zurück.

**Response:**
```json
{
  "status": "ok",
  "display_controller": "aktiv",
  "config_loaded": true
}
```

### GET /tickers
Zeigt alle konfigurierten Ticker an.

**Response:**
```json
{
  "stocks": ["AAPL", "GOOGL"],
  "crypto": ["BTC-USD", "ETH-USD"]
}
```

### POST /tickers
Fügt einen neuen Ticker hinzu.

**Request:**
```json
{
  "symbol": "AAPL",
  "type": "stock"
}
```

### DELETE /tickers/{symbol}
Entfernt einen Ticker.

### GET /news
Zeigt den aktuellen News-Feed an.

### POST /news
Setzt einen neuen News-Feed.

**Request:**
```json
{
  "feed_url": "https://news.google.com/rss"
}
```

## 🎯 Aktueller Status

### ✅ Funktioniert:
- ChuckBuilds Display Controller läuft erfolgreich
- Web-Interface ist erreichbar auf Port 8000
- Fallback-Modus funktioniert ohne Hardware
- Alle API-Endpunkte sind verfügbar
- Deutsche Lokalisierung aktiv

### 🔧 Bekannte Einschränkungen:
- RGBMatrix-Bibliothek nicht verfügbar (verwendet Fallback)
- Hardware-Tests noch nicht durchgeführt
- Erweiterte ChuckBuilds-Features (Sport, Wetter) deaktiviert

### 🚀 Nächste Schritte:
1. Hardware-Tests mit echter RGB-Matrix
2. Erweiterte Features aktivieren
3. Performance-Optimierungen
4. Zusätzliche Konfigurationsoptionen

## 🤝 Beitragen

1. Fork das Repository
2. Erstelle einen Feature-Branch (`git checkout -b feature/AmazingFeature`)
3. Committe deine Änderungen (`git commit -m 'Add some AmazingFeature'`)
4. Push zum Branch (`git push origin feature/AmazingFeature`)
5. Öffne einen Pull Request

## 📄 Lizenz

Dieses Projekt basiert auf dem [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) Projekt und ist unter der gleichen Lizenz verfügbar.

## 🙏 Danksagungen

- [ChuckBuilds/LEDMatrix](https://github.com/ChuckBuilds/LEDMatrix) für das erweiterte Display-System
- [rpi-rgb-led-matrix](https://github.com/hzeller/rpi-rgb-led-matrix) für die ursprüngliche Hardware-Unterstützung
- Alle Mitwirkenden und Community-Mitglieder

---

**Letzte Aktualisierung:** $(date +"%Y-%m-%d %H:%M:%S")
**Status:** ✅ ChuckBuilds-System läuft erfolgreich
**Version:** 2.0.0 (ChuckBuilds-Integration)
