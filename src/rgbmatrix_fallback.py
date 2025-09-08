"""Fallback-Implementation für rgbmatrix-Bibliothek ohne Hardware."""

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class RGBMatrixOptions:
    """Fallback für RGBMatrixOptions."""
    def __init__(self):
        self.rows = 32
        self.cols = 64
        self.chain_length = 2
        self.parallel = 1
        self.brightness = 95
        self.hardware_mapping = 'adafruit-hat-pwm'
        self.scan_mode = 0
        self.pwm_bits = 9
        self.pwm_dither_bits = 1
        self.pwm_lsb_nanoseconds = 130
        self.disable_hardware_pulsing = False
        self.inverse_colors = False
        self.show_refresh_rate = False
        self.limit_refresh_rate_hz = 120
        self.gpio_slowdown = 3
        self.led_rgb_sequence = 'RGB'
        self.pixel_mapper_config = ''
        self.row_address_type = 0
        self.multiplexing = 0

class RGBMatrix:
    """Fallback für RGBMatrix ohne Hardware."""
    
    def __init__(self, options: RGBMatrixOptions = None):
        self.options = options or RGBMatrixOptions()
        self.width = self.options.cols * self.options.chain_length
        self.height = self.options.rows
        logger.warning("RGBMatrix Fallback-Modus aktiviert - keine echte Hardware")
        print(f"DISPLAY: RGB Matrix Fallback aktiviert ({self.width}x{self.height})")
    
    def CreateFrameCanvas(self):
        """Erstelle einen Fallback-Canvas."""
        return RGBMatrixCanvas(self.width, self.height)

class RGBMatrixCanvas:
    """Fallback für RGBMatrix Canvas."""
    
    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height
        self._pixels = [[(0, 0, 0) for _ in range(width)] for _ in range(height)]
    
    def Clear(self):
        """Canvas leeren."""
        self._pixels = [[(0, 0, 0) for _ in range(self.width)] for _ in range(self.height)]
    
    def SetPixel(self, x: int, y: int, r: int, g: int, b: int):
        """Pixel setzen."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self._pixels[y][x] = (r, g, b)
    
    def Fill(self, r: int, g: int, b: int):
        """Canvas füllen."""
        self._pixels = [[(r, g, b) for _ in range(self.width)] for _ in range(self.height)]

# Mock graphics module
class graphics:
    """Fallback für graphics module."""
    
    class Color:
        def __init__(self, r: int, g: int, b: int):
            self.r = r
            self.g = g
            self.b = b
    
    class Font:
        def __init__(self):
            self.height = 8
        
        def LoadFont(self, path: str):
            logger.debug(f"Font geladen (Fallback): {path}")
            return True
        
        def CharacterWidth(self, char: str) -> int:
            return 6  # Standard-Zeichenbreite
        
        def DrawText(self, canvas, font, x: int, y: int, color, text: str):
            """Text zeichnen (Fallback)."""
            logger.debug(f"Text gezeichnet (Fallback): '{text}' bei ({x}, {y})")
            print(f"DISPLAY: {text}")

# Export für Import
RGBMatrix = RGBMatrix
RGBMatrixOptions = RGBMatrixOptions
graphics = graphics
