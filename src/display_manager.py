"""Display Manager mit Fallback-Unterstützung."""

import logging
import time
from typing import Dict, Any, List, Tuple
import math
import os
import freetype

# Versuche echte rgbmatrix-Bibliothek zu importieren, sonst Fallback
try:
    from rgbmatrix import RGBMatrix, RGBMatrixOptions, graphics
    logger = logging.getLogger(__name__)
    logger.info("Echte rgbmatrix-Bibliothek geladen")
except ImportError:
    from .rgbmatrix_fallback import RGBMatrix, RGBMatrixOptions, graphics
    logger = logging.getLogger(__name__)
    logger.warning("rgbmatrix-Bibliothek nicht verfügbar, verwende Fallback")

from .weather_icons import WeatherIcons

logger.setLevel(logging.INFO)

class DisplayManager:
    _instance = None
    _initialized = False

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(DisplayManager, cls).__new__(cls)
        return cls._instance

    def __init__(self, config: Dict[str, Any] = None, force_fallback: bool = False, suppress_test_pattern: bool = False):
        start_time = time.time()
        self.config = config or {}
        self._force_fallback = force_fallback
        self._suppress_test_pattern = suppress_test_pattern
        self._snapshot_path = "/tmp/led_matrix_preview.png"
        self._snapshot_min_interval_sec = 0.2
        self._last_snapshot_ts = 0.0
        self._setup_matrix()
        logger.info("Matrix setup completed in %.3f seconds", time.time() - start_time)
        
        font_time = time.time()
        self._load_fonts()
        logger.info("Font loading completed in %.3f seconds", time.time() - font_time)

    def _setup_matrix(self):
        """Initialize the RGB matrix with configuration settings."""
        setup_start = time.time()
        
        try:
            if getattr(self, '_force_fallback', False):
                raise RuntimeError('Forced fallback mode requested')
            
            options = RGBMatrixOptions()
            
            # Hardware configuration
            hardware_config = self.config.get('display', {}).get('hardware', {})
            runtime_config = self.config.get('display', {}).get('runtime', {})
            
            # Basic hardware settings
            options.rows = hardware_config.get('rows', 32)
            options.cols = hardware_config.get('cols', 64)
            options.chain_length = hardware_config.get('chain_length', 2)
            options.parallel = hardware_config.get('parallel', 1)
            options.hardware_mapping = hardware_config.get('hardware_mapping', 'adafruit-hat-pwm')
            
            # Performance and stability settings
            options.brightness = hardware_config.get('brightness', 90)
            options.pwm_bits = hardware_config.get('pwm_bits', 10)
            options.pwm_lsb_nanoseconds = hardware_config.get('pwm_lsb_nanoseconds', 150)
            options.led_rgb_sequence = hardware_config.get('led_rgb_sequence', 'RGB')
            options.pixel_mapper_config = hardware_config.get('pixel_mapper_config', '')
            options.row_address_type = hardware_config.get('row_address_type', 0)
            options.multiplexing = hardware_config.get('multiplexing', 0)
            options.disable_hardware_pulsing = hardware_config.get('disable_hardware_pulsing', False)
            options.show_refresh_rate = hardware_config.get('show_refresh_rate', False)
            options.limit_refresh_rate_hz = hardware_config.get('limit_refresh_rate_hz', 90)
            options.gpio_slowdown = runtime_config.get('gpio_slowdown', 2)
            
            # Additional settings from config
            if 'scan_mode' in hardware_config:
                options.scan_mode = hardware_config.get('scan_mode')
            if 'pwm_dither_bits' in hardware_config:
                options.pwm_dither_bits = hardware_config.get('pwm_dither_bits')
            if 'inverse_colors' in hardware_config:
                options.inverse_colors = hardware_config.get('inverse_colors')
            
            logger.info(f"Initializing RGB Matrix with settings: rows={options.rows}, cols={options.cols}, chain_length={options.chain_length}, parallel={options.parallel}, hardware_mapping={options.hardware_mapping}")
            
            # Initialize the matrix
            self.matrix = RGBMatrix(options=options)
            logger.info("RGB Matrix initialized successfully")
            
            # Create double buffer for smooth updates
            self.offscreen_canvas = self.matrix.CreateFrameCanvas()
            self.current_canvas = self.matrix.CreateFrameCanvas()
            logger.info("Frame canvases created successfully")
            
            # Create image with full chain width
            self.image = None  # Wird bei Bedarf erstellt
            self.draw = None
            logger.info(f"Image canvas created with dimensions: {self.matrix.width}x{self.matrix.height}")
            
        except Exception as e:
            logger.warning(f"Failed to initialize RGB Matrix: {e}")
            logger.info("Falling back to console output mode")
            self._setup_fallback()
        
        logger.info("Matrix setup completed in %.3f seconds", time.time() - setup_start)

    def _setup_fallback(self):
        """Setup fallback mode for development without hardware."""
        logger.info("Setting up fallback mode")
        
        # Create a mock matrix
        options = RGBMatrixOptions()
        options.rows = 32
        options.cols = 64
        options.chain_length = 2
        options.parallel = 1
        options.hardware_mapping = 'adafruit-hat-pwm'
        
        self.matrix = RGBMatrix(options=options)
        self.offscreen_canvas = self.matrix.CreateFrameCanvas()
        self.current_canvas = self.matrix.CreateFrameCanvas()
        self.image = None
        self.draw = None
        
        logger.info("Fallback mode setup complete")

    def _load_fonts(self):
        """Load fonts for text rendering."""
        try:
            # Font paths
            font_paths = [
                "assets/fonts/PressStart2P-Regular.ttf",
                "assets/fonts/press-start-2p.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/System/Library/Fonts/Arial.ttf"
            ]
            
            self.fonts = {}
            for size in [6, 8, 10, 12, 14, 16, 18, 20]:
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        try:
                            self.fonts[size] = freetype.Face(font_path)
                            logger.info(f"Loaded font {font_path} for size {size}")
                            break
                        except Exception as e:
                            logger.debug(f"Failed to load font {font_path}: {e}")
                            continue
            
            if not self.fonts:
                logger.warning("No fonts loaded, text rendering may not work properly")
                
        except Exception as e:
            logger.error(f"Error loading fonts: {e}")
            self.fonts = {}

    def clear(self):
        """Clear the display."""
        if hasattr(self, 'offscreen_canvas'):
            self.offscreen_canvas.Clear()

    def set_pixel(self, x: int, y: int, r: int, g: int, b: int):
        """Set a pixel color."""
        if hasattr(self, 'offscreen_canvas'):
            self.offscreen_canvas.SetPixel(x, y, r, g, b)

    def draw_text(self, x: int, y: int, text: str, color: Tuple[int, int, int] = (255, 255, 255), font_size: int = 8):
        """Draw text on the display."""
        if hasattr(self, 'offscreen_canvas') and hasattr(self, 'fonts'):
            font = self.fonts.get(font_size)
            if font:
                try:
                    # Vereinfachte Text-Darstellung
                    for i, char in enumerate(text):
                        char_x = x + (i * 6)  # Einfache Zeichenbreite
                        if char_x < self.matrix.width:
                            # Einfache Pixel-Darstellung für jeden Buchstaben
                            for dy in range(font_size):
                                for dx in range(6):
                                    if char_x + dx < self.matrix.width and y + dy < self.matrix.height:
                                        self.set_pixel(char_x + dx, y + dy, *color)
                except Exception as e:
                    logger.error(f"Error drawing text: {e}")

    def swap(self):
        """Swap the display buffers."""
        if hasattr(self, 'matrix') and hasattr(self, 'offscreen_canvas') and hasattr(self, 'current_canvas'):
            try:
                self.current_canvas = self.matrix.SwapOnVSync(self.offscreen_canvas)
                self.offscreen_canvas = self.matrix.CreateFrameCanvas()
            except Exception as e:
                logger.debug(f"Error swapping buffers: {e}")

    def get_width(self):
        """Get display width."""
        return getattr(self.matrix, 'width', 128)

    def get_height(self):
        """Get display height."""
        return getattr(self.matrix, 'height', 32)
