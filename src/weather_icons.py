import os
from typing import Union
from PIL import Image, ImageDraw
# math is no longer needed for drawing, remove if not used elsewhere
# import math 

class WeatherIcons:
    ICON_DIR = "assets/weather/"  # Path where PNG icons are stored
    DEFAULT_ICON = "not-available.png"
    DEFAULT_SIZE = 64 # Default size, should match icons but can be overridden

    # Mapping from OpenWeatherMap icon codes to our filenames
    # See: https://openweathermap.org/weather-conditions#Icon-list
    ICON_MAP = {
        # Day icons
        "01d": "clear-day.png",
        "02d": "partly-cloudy-day.png",  # Few clouds
        "03d": "cloudy.png",             # Scattered clouds
        "04d": "overcast-day.png",       # Broken clouds / Overcast
        "09d": "drizzle.png",            # Shower rain (using drizzle)
        "10d": "partly-cloudy-day-rain.png", # Rain
        "11d": "thunderstorms-day.png",  # Thunderstorm
        "13d": "partly-cloudy-day-snow.png", # Snow
        "50d": "mist.png",               # Mist (can use fog, haze etc. too)

        # Night icons
        "01n": "clear-night.png",
        "02n": "partly-cloudy-night.png",# Few clouds
        "03n": "cloudy.png",             # Scattered clouds (same as day)
        "04n": "overcast-night.png",     # Broken clouds / Overcast
        "09n": "drizzle.png",            # Shower rain (using drizzle, same as day)
        "10n": "partly-cloudy-night-rain.png", # Rain
        "11n": "thunderstorms-night.png", # Thunderstorm
        "13n": "partly-cloudy-night-snow.png", # Snow
        "50n": "mist.png",               # Mist (same as day)

        # Add mappings for specific conditions if needed, although OWM codes are preferred
        "tornado": "tornado.png",
        "hurricane": "hurricane.png",
        "wind": "wind.png", # Generic wind if code is not specific enough
    }

    @staticmethod
    def _get_icon_filename(icon_code: str) -> str:
        """Maps an OpenWeatherMap icon code (e.g., '01d', '10n') to an icon filename."""
        filename = WeatherIcons.ICON_MAP.get(icon_code, WeatherIcons.DEFAULT_ICON)
        print(f"[WeatherIcons] Mapping icon code '{icon_code}' to filename: '{filename}'")

        # Check if the mapped filename exists, otherwise use default
        potential_path = os.path.join(WeatherIcons.ICON_DIR, filename)
        if not os.path.exists(potential_path):
            # If a specific icon was determined but not found, log warning and use default
            if filename != WeatherIcons.DEFAULT_ICON:
                print(f"Warning: Mapped icon file '{filename}' not found at '{potential_path}'. Falling back to default.")
                filename = WeatherIcons.DEFAULT_ICON
            
            # Check if default exists
            default_path = os.path.join(WeatherIcons.ICON_DIR, WeatherIcons.DEFAULT_ICON)
            if not os.path.exists(default_path):
                 print(f"Error: Default icon file also not found: {default_path}")
                 # Allow filename to remain DEFAULT_ICON name, load_weather_icon handles FileNotFoundError

        return filename

    @staticmethod
    def load_weather_icon(icon_code: str, size: int = DEFAULT_SIZE) -> Union[Image.Image, None]:
        """Loads, converts, and resizes the appropriate weather icon based on the OWM code. Returns None on failure."""
        filename = WeatherIcons._get_icon_filename(icon_code)
        icon_path = os.path.join(WeatherIcons.ICON_DIR, filename)

        try:
            # Open image and ensure it's RGBA for transparency handling
            icon_img = Image.open(icon_path).convert("RGBA")

            # Resize if necessary using high-quality downsampling (LANCZOS/ANTIALIAS)
            if icon_img.width != size or icon_img.height != size:
                icon_img = icon_img.resize((size, size), Image.Resampling.LANCZOS)

            return icon_img
        except FileNotFoundError:
            print(f"Error: Icon file not found: {icon_path}")
            # Don't try to load default here, _get_icon_filename already handled fallback logic
            return None
        except Exception as e:
            print(f"Error processing icon {icon_path}: {e}")
            return None

    @staticmethod
    def draw_weather_icon(image: Image.Image, icon_code: str, x: int, y: int, size: int = DEFAULT_SIZE):
         """Loads the appropriate weather icon based on OWM code and pastes it onto the target PIL Image object."""
         icon_to_draw = WeatherIcons.load_weather_icon(icon_code, size)
         if icon_to_draw:
             # Create a thresholded mask from the icon's alpha channel
             # to remove faint anti-aliasing pixels when pasting on black bg.
             # Pixels with alpha > 200 will be fully opaque, others fully transparent.
             try:
                 # alpha = icon_to_draw.getchannel('A')
                 # # Apply threshold: lambda function returns 255 if input > 200, else 0
                 # threshold_mask = alpha.point(lambda p: 255 if p > 200 else 0)
                 
                 # Paste the icon using the thresholded mask
                 # image.paste(icon_to_draw, (x, y), threshold_mask)
                 
                 # Paste the icon directly with its original alpha channel
                 image.paste(icon_to_draw, (x, y), icon_to_draw)
             except Exception as e:
                 print(f"Error processing or pasting icon for code '{icon_code}' at ({x},{y}): {e}")
                 # Fallback or alternative handling if needed
                 # try:
                 #    # Fallback: Try pasting with original alpha if thresholding fails
                 #    image.paste(icon_to_draw, (x, y), icon_to_draw)
                 # except Exception as e2:
                 #    print(f"Error during fallback paste: {e2}")
                 pass
         else:
             # Optional: Draw a placeholder if icon loading fails completely
             print(f"Could not load icon for code '{icon_code}' to draw at ({x},{y})")

    @staticmethod
    def draw_sun(draw: ImageDraw, x: int, y: int, size: int = 16, color: tuple = (255, 200, 0)):
        """Draw a sun icon with rays."""
        center_x = x + size // 2
        center_y = y + size // 2
        radius = size // 3
        
        # Draw main sun circle
        draw.ellipse([
            center_x - radius, center_y - radius,
            center_x + radius, center_y + radius
        ], fill=color)
        
        # Draw rays
        ray_length = size // 4
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            start_x = center_x + (radius * math.cos(rad))
            start_y = center_y + (radius * math.sin(rad))
            end_x = center_x + ((radius + ray_length) * math.cos(rad))
            end_y = center_y + ((radius + ray_length) * math.sin(rad))
            draw.line([start_x, start_y, end_x, end_y], fill=color, width=2)

    @staticmethod
    def draw_cloud(draw: ImageDraw, x: int, y: int, size: int = 16, color: tuple = (200, 200, 200)):
        """Draw a cloud icon."""
        # Draw multiple circles to form cloud shape
        circle_size = size // 2
        positions = [
            (x + size//4, y + size//3),
            (x + size//2, y + size//3),
            (x + size//3, y + size//6)
        ]
        
        for pos_x, pos_y in positions:
            draw.ellipse([
                pos_x, pos_y,
                pos_x + circle_size, pos_y + circle_size
            ], fill=color)

    @staticmethod
    def draw_rain(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw rain icon with cloud and droplets."""
        # Draw cloud first
        WeatherIcons.draw_cloud(draw, x, y, size)
        
        # Draw rain drops
        drop_color = (0, 150, 255)  # Light blue
        drop_length = size // 3
        drop_spacing = size // 4
        
        for i in range(3):
            drop_x = x + size//4 + (i * drop_spacing)
            drop_y = y + size//2
            draw.line([
                drop_x, drop_y,
                drop_x - 2, drop_y + drop_length
            ], fill=drop_color, width=2)

    @staticmethod
    def draw_snow(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw snow icon with cloud and snowflakes."""
        # Draw cloud first
        WeatherIcons.draw_cloud(draw, x, y, size)
        
        # Draw snowflakes
        snow_color = (200, 200, 255)  # Light blue-white
        flake_size = size // 6
        flake_spacing = size // 4
        
        for i in range(3):
            center_x = x + size//4 + (i * flake_spacing)
            center_y = y + size//2
            
            # Draw 6-point snowflake
            for angle in range(0, 360, 60):
                rad = math.radians(angle)
                end_x = center_x + (flake_size * math.cos(rad))
                end_y = center_y + (flake_size * math.sin(rad))
                draw.line([center_x, center_y, end_x, end_y], fill=snow_color, width=1)

    @staticmethod
    def draw_thunderstorm(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw thunderstorm icon with cloud and lightning."""
        # Draw dark cloud
        WeatherIcons.draw_cloud(draw, x, y, size, color=(100, 100, 100))
        
        # Draw lightning bolt
        lightning_color = (255, 255, 0)  # Yellow
        bolt_points = [
            (x + size//2, y + size//3),
            (x + size//2 - size//4, y + size//2),
            (x + size//2, y + size//2),
            (x + size//2 - size//4, y + size//2 + size//4)
        ]
        draw.line(bolt_points, fill=lightning_color, width=2)

    @staticmethod
    def draw_mist(draw: ImageDraw, x: int, y: int, size: int = 16):
        """Draw mist/fog icon."""
        mist_color = (200, 200, 200)  # Light gray
        wave_height = size // 4
        wave_spacing = size // 3
        
        for i in range(3):
            wave_y = y + size//3 + (i * wave_spacing)
            draw.line([
                x + size//4, wave_y,
                x + size//4 + size//2, wave_y + wave_height
            ], fill=mist_color, width=2) 