"""Matrix display abstraction for RGB LED matrix panels.

Wraps `rgbmatrix` (from rpi-rgb-led-matrix). Wenn nicht verfügbar,
fällt auf Konsolen-Output zurück.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

LOGGER = logging.getLogger(__name__)

try:  # Hardware-Bibliothek evtl. nicht installiert
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics  # type: ignore
except Exception:  # pragma: no cover
    RGBMatrix = None          # type: ignore
    RGBMatrixOptions = None   # type: ignore
    graphics = None           # type: ignore


class MatrixDisplay:
    """Simple wrapper for a chain of 64x32 RGB LED matrix panels.

    Parameters
    ----------
    width : int
        Gesamtbreite der virtuellen Anzeige (z. B. 128 bei 2x 64px).
    height : int
        Höhe der Anzeige (z. B. 32).
    chain_length : int
        Anzahl der horizontal verketteten Panels (z. B. 2).
    hardware_mapping : str
        Mapping für dein HAT (z. B. "adafruit-hat", "regular").
    """

    def __init__(
        self,
        width: int = 128,
        height: int = 32,
        chain_length: int = 2,
        hardware_mapping: str = "adafruit-hat",
    ) -> None:
        self.width = width
        self.height = height
        self.chain_length = chain_length
        self._brightness = 100

        if RGBMatrix:
            options = RGBMatrixOptions()
            options.rows = height
            options.cols = width // chain_length
            options.chain_length = chain_length
            options.parallel = 1
            options.hardware_mapping = hardware_mapping

            self.matrix = RGBMatrix(options=options)
            try:
                self.matrix.brightness = self._brightness
            except Exception:
                pass
            LOGGER.debug("RGBMatrix initialized")
        else:  # pragma: no cover
            self.matrix = None
            LOGGER.warning("rgbmatrix not available; using console fallback")

    # ------------------------------------------------------------------
    def _find_font_path(self) -> Optional[str]:
        """Finde eine nutzbare .bdf-Schrift. Gibt None zurück, wenn keine da."""
        # Häufige Pfade:
        candidates = [
            # rpi-rgb-led-matrix Beispiel-Fonts (falls Repo installiert/cloned)
            "/usr/local/share/rpi-rgb-led-matrix/fonts/7x13.bdf",
            "/usr/share/rpi-rgb-led-matrix/fonts/7x13.bdf",
            # Projekt-lokale Fonts (falls du einen reinlegst)
            os.path.join(os.path.dirname(__file__), "fonts", "7x13.bdf"),
            os.path.join(os.path.dirname(__file__), "fonts", "6x10.bdf"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def show_message(self, message: str) -> None:
        """Scrollt `message` über das Display (oder printet sie im Fallback)."""
        if not message:
            return

        if self.matrix is None or graphics is None:  # Fallback: Konsole
            print(f"DISPLAY: {message}")
            return

        font_path = self._find_font_path()
        if not font_path:
            # Kein Font verfügbar → simpler Fallback
            print(f"DISPLAY(no-font): {message}")
            return

        # Zeichnen auf echter Hardware
        canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont(font_path)
        color = graphics.Color(255, 255, 0)

        # Zeichenbreite grob: ~6px bei 7x13, konservativ 6 * len
        pos = canvas.width
        baseline = min(self.height - 4, 20)  # 20 ist oft gut bei 32px Höhe
        text_px_width = len(message) * 6

        while pos + text_px_width >= 0:
            canvas.Clear()
            graphics.DrawText(canvas, font, pos, baseline, color, message)
            pos -= 1
            canvas = self.matrix.SwapOnVSync(canvas)

        LOGGER.debug("Displayed message: %s", message)

    # ------------------------------------------------------------------
    def set_brightness(self, value: int) -> None:
        """Setzt Helligkeit (0..100)."""
        try:
            value = int(value)
        except Exception:
            value = 100
        value = max(0, min(100, value))
        self._brightness = value
        if self.matrix:  # pragma: no cover
            try:
                self.matrix.brightness = value
            except Exception:
                pass
        else:
            LOGGER.info("Set brightness (fallback) to %s", value)

    @property
    def brightness(self) -> int:
        return self._brightness
