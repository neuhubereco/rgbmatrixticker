"""Matrix display abstraction for RGB LED matrix panels.

This module wraps the `rgbmatrix` library used on Raspberry Pi to drive
LED panels.  When the library is not available (e.g. during testing), it
falls back to printing messages to the console so the rest of the
application can be exercised without hardware.
"""

from __future__ import annotations

import logging
from typing import Optional

try:  # pragma: no cover - hardware library may not be installed
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
except Exception:  # pragma: no cover
    RGBMatrix = None  # type: ignore
    RGBMatrixOptions = None  # type: ignore
    graphics = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class MatrixDisplay:
    """Simple wrapper for a chain of 64x32 RGB LED matrix panels.

    Parameters
    ----------
    width: int
        Total width of the virtual display.  Two 64x32 panels side by side
        therefore result in ``width=128``.
    height: int
        Height of the display.  The panels used in this project are 32
        pixels high.
    chain_length: int
        Number of panels chained horizontally.  For ``width=128`` and
        ``height=32`` this should be ``2``.
    """

    def __init__(self, width: int = 128, height: int = 32, chain_length: int = 2) -> None:
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
            options.hardware_mapping = "adafruit-hat"
            self.matrix = RGBMatrix(options=options)
            self.matrix.brightness = self._brightness
            LOGGER.debug("RGBMatrix initialized: %s", self.matrix)
        else:  # pragma: no cover
            self.matrix = None
            LOGGER.warning(
                "rgbmatrix library not available; falling back to console output"
            )

    # ------------------------------------------------------------------
    def show_message(self, message: str) -> None:
        """Display ``message`` on the matrix.

        On actual hardware the message scrolls from right to left.  In test
        environments the message is printed to STDOUT.
        """

        if self.matrix is None:  # pragma: no cover - console fallback
            print(f"DISPLAY: {message}")
            return

        # Real hardware drawing: scroll the text across the display.
        canvas = self.matrix.CreateFrameCanvas()
        font = graphics.Font()
        font.LoadFont("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.bdf")
        text_color = graphics.Color(255, 255, 0)
        pos = canvas.width
        while pos + len(message) * 6 >= 0:
            canvas.Clear()
            graphics.DrawText(canvas, font, pos, 20, text_color, message)
            pos -= 1
            canvas = self.matrix.SwapOnVSync(canvas)
        LOGGER.debug("Displayed message: %s", message)

    # ------------------------------------------------------------------
    def set_brightness(self, value: int) -> None:
        """Set display brightness from 0 to 100."""

        value = max(0, min(100, int(value)))
        self._brightness = value
        if self.matrix:  # pragma: no cover - hardware interaction
            self.matrix.brightness = value
        else:
            LOGGER.info("Set brightness to %s", value)

    @property
    def brightness(self) -> int:
        return self._brightness

