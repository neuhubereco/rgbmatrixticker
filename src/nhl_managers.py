import os
import time
import logging
import requests
import json
from typing import Dict, Any, Optional, List
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from datetime import datetime, timedelta, timezone
from src.display_manager import DisplayManager
from src.cache_manager import CacheManager
from src.config_manager import ConfigManager
from src.odds_manager import OddsManager
import pytz

# Import the API counter function from web interface
try:
    from web_interface_v2 import increment_api_counter
except ImportError:
    # Fallback if web interface is not available
    def increment_api_counter(kind: str, count: int = 1):
        pass

# Constants
NHL_API_BASE_URL = "https://api-web.nhle.com/v1/schedule/"

# Configure logging to match main configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

class BaseNHLManager:
    """Base class for NHL managers with common functionality."""
    # Class variables for warning tracking
    _no_data_warning_logged = False
    _last_warning_time = 0
    _warning_cooldown = 60  # Only log warnings once per minute
    _shared_data = None
    _last_shared_update = 0
    
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        self.display_manager = display_manager
        self.config_manager = ConfigManager()
        self.config = config
        self.cache_manager = cache_manager
        self.odds_manager = OddsManager(self.cache_manager, self.config)
        self.logger = logging.getLogger(__name__)
        self.nhl_config = config.get("nhl_scoreboard", {})
        self.is_enabled = self.nhl_config.get("enabled", False)
        self.show_odds = self.nhl_config.get("show_odds", False)
        self.test_mode = self.nhl_config.get("test_mode", False)  # Use test_mode from config
        self.logo_dir = self.nhl_config.get("logo_dir", "assets/sports/nhl_logos")
        self.update_interval = self.nhl_config.get("update_interval_seconds", 60)
        self.show_records = self.nhl_config.get('show_records', False)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.nhl_config.get("favorite_teams", [])
        self.recent_hours = self.nhl_config.get("recent_game_hours", 48)  # Default 48 hours
        
        # Set logging level to DEBUG to see all messages
        self.logger.setLevel(logging.DEBUG)
        
        # Get display dimensions from config
        display_config = config.get("display", {})
        hardware_config = display_config.get("hardware", {})
        cols = hardware_config.get("cols", 64)
        chain = hardware_config.get("chain_length", 1)
        self.display_width = int(cols * chain)
        self.display_height = hardware_config.get("rows", 32)
        
        # Cache for loaded logos
        self._logo_cache = {}
        
        self.logger.info(f"Initialized NHL manager with display dimensions: {self.display_width}x{self.display_height}")
        self.logger.info(f"Logo directory: {self.logo_dir}")

    def _fetch_odds(self, game: Dict) -> None:
        """Fetch odds for a game and attach it to the game dictionary."""
        # Check if odds should be shown for this sport
        if not self.show_odds:
            return

        # Check if we should only fetch for favorite teams
        is_favorites_only = self.nhl_config.get("show_favorite_teams_only", False)
        if is_favorites_only:
            home_abbr = game.get('home_abbr')
            away_abbr = game.get('away_abbr')
            if not (home_abbr in self.favorite_teams or away_abbr in self.favorite_teams):
                self.logger.debug(f"Skipping odds fetch for non-favorite game in favorites-only mode: {away_abbr}@{home_abbr}")
                return

        self.logger.debug(f"Proceeding with odds fetch for game: {game.get('id', 'N/A')}")
        
        try:
            odds_data = self.odds_manager.get_odds(
                sport="hockey",
                league="nhl",
                event_id=game["id"]
            )
            if odds_data:
                game['odds'] = odds_data
        except Exception as e:
            self.logger.error(f"Error fetching odds for game {game.get('id', 'N/A')}: {e}")

    def _get_timezone(self):
        try:
            return pytz.timezone(self.config_manager.get_timezone())
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    def _fetch_nhl_api_data(self, use_cache: bool = True) -> Optional[Dict]:
        """Fetch and cache data from the NHL API."""
        current_time = time.time()
        
        # Use today's date for the request
        date_str = datetime.now(self._get_timezone()).strftime('%Y-%m-%d')
        cache_key = f"nhl_api_data_{date_str}"

        # If using cache, try to load from cache first
        if use_cache:
            cached_data = self.cache_manager.get(cache_key, max_age=300)
            if cached_data:
                self.logger.info(f"[NHL] Using cached data for {date_str}")
                return cached_data
                
        try:
            # If not in cache or stale, or if cache is disabled, fetch from API
            url = f"{NHL_API_BASE_URL}{date_str}"
            self.logger.info(f"Fetching data from URL: {url}")
            
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            # Increment API counter for sports data call
            increment_api_counter('sports', 1)
            
            self.logger.info(f"[NHL] Successfully fetched data from NHL API for {date_str}")
            
            # Save to cache if caching is enabled
            if use_cache:
                self.cache_manager.set(cache_key, data)
            
            return data
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[NHL] Error fetching data from NHL API: {e}")
            return None

    def _fetch_data(self, date_str: str = None) -> Optional[Dict]:
        """Fetch data using the new centralized method."""
        # For live games, bypass the shared cache to ensure fresh data
        if isinstance(self, NHLLiveManager):
            return self._fetch_nhl_api_data(use_cache=False)
        else:
            # For non-live games, use the shared cache
            return self._fetch_nhl_api_data(use_cache=True)

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 12)
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
            logging.info("[NHL] Successfully loaded Press Start 2P font for all text elements")
        except IOError:
            logging.warning("[NHL] Press Start 2P font not found, trying 4x6 font.")
            try:
                # Try to load the 4x6 font as a fallback
                fonts['score'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 12)
                fonts['time'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
                fonts['team'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 8)
                fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 9)
                logging.info("[NHL] Successfully loaded 4x6 font for all text elements")
            except IOError:
                logging.warning("[NHL] 4x6 font not found, using default PIL font.")
                # Use default PIL font as a last resort
                fonts['score'] = ImageFont.load_default()
                fonts['time'] = ImageFont.load_default()
                fonts['team'] = ImageFont.load_default()
                fonts['status'] = ImageFont.load_default()
        return fonts

    def _draw_text_with_outline(self, draw, text, position, font, fill=(255, 255, 255), outline_color=(0, 0, 0)):
        """
        Draw text with a black outline for better readability.
        
        Args:
            draw: ImageDraw object
            text: Text to draw
            position: (x, y) position to draw the text
            font: Font to use
            fill: Text color (default: white)
            outline_color: Outline color (default: black)
        """
        x, y = position
        
        # Draw the outline by drawing the text in black at 8 positions around the text
        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        
        # Draw the text in the specified color
        draw.text((x, y), text, font=font, fill=fill)

    def _load_and_resize_logo(self, team_abbrev: str) -> Optional[Image.Image]:
        """Load and resize a team logo, with caching."""
        # self.logger.debug(f"Loading logo for {team_abbrev}") # Commented out
        
        if team_abbrev in self._logo_cache:
            # self.logger.debug(f"Using cached logo for {team_abbrev}") # Commented out
            return self._logo_cache[team_abbrev]
            
        logo_path = os.path.join(self.logo_dir, f"{team_abbrev}.png")
        self.logger.debug(f"Logo path: {logo_path}")
        
        try:
            # Create test logos if they don't exist
            if not os.path.exists(logo_path):
                self.logger.info(f"Creating test logo for {team_abbrev}")
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                # Create a simple colored rectangle as a test logo
                logo = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
                draw = ImageDraw.Draw(logo)
                # Use team abbreviation to determine color
                if team_abbrev == "TB":
                    color = (0, 0, 255, 255)  # Blue for Tampa Bay
                else:
                    color = (255, 0, 0, 255)  # Red for Dallas
                draw.rectangle([4, 4, 28, 28], fill=color)
                # Add team abbreviation
                draw.text((8, 8), team_abbrev, fill=(255, 255, 255, 255))
                logo.save(logo_path)
                self.logger.info(f"Created test logo at {logo_path}")
            
            logo = Image.open(logo_path)
            self.logger.debug(f"Opened logo for {team_abbrev}, size: {logo.size}, mode: {logo.mode}")
            
            # Convert to RGBA if not already
            if logo.mode != 'RGBA':
                self.logger.debug(f"Converting {team_abbrev} logo from {logo.mode} to RGBA")
                logo = logo.convert('RGBA')
            
            # Calculate max size based on display dimensions
            # Make logos 150% of display width to allow them to extend off screen
            max_width = int(self.display_width * 1.5)
            max_height = int(self.display_height * 1.5)
            
            # Resize maintaining aspect ratio
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self.logger.debug(f"Resized {team_abbrev} logo to {logo.size}")
            
            # Cache the resized logo
            self._logo_cache[team_abbrev] = logo
            return logo
            
        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbrev}: {e}", exc_info=True)
            return None

    def _extract_game_details(self, game_event: Dict) -> Optional[Dict]:
        """Extract relevant game details from ESPN API response."""
        if not game_event:
            return None

        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]

            # Parse game date/time
            try:
                start_time_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
                self.logger.debug(f"[NHL] Parsed game time: {start_time_utc}")
            except ValueError:
                logging.warning(f"[NHL] Could not parse game date: {game_date_str}")
                start_time_utc = None

            home_team = next(c for c in competitors if c.get("homeAway") == "home")
            away_team = next(c for c in competitors if c.get("homeAway") == "away")
            home_record = home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else ''
            away_record = away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else ''
            
            # Don't show "0-0" records - set to blank instead
            if home_record == "0-0":
                home_record = ''
            if away_record == "0-0":
                away_record = ''

            # Format game time and date for display
            game_time = ""
            game_date = ""
            if start_time_utc:
                # Convert to local time
                local_time = start_time_utc.astimezone(self._get_timezone())
                game_time = local_time.strftime("%-I:%M%p")
                
                # Check date format from config
                use_short_date_format = self.config.get('display', {}).get('use_short_date_format', False)
                if use_short_date_format:
                    game_date = local_time.strftime("%-m/%-d")
                else:
                    game_date = self.display_manager.format_date_with_ordinal(local_time)

            details = {
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"],
                "period": status.get("period", 0),
                "clock": status.get("displayClock", "0:00"),
                "is_live": status["type"]["state"] in ("in", "halftime"),
                "is_final": status["type"]["state"] == "post",
                "is_upcoming": status["type"]["state"] == "pre",
                "home_abbr": home_team["team"]["abbreviation"],
                "home_score": home_team.get("score", "0"),
                "home_record": home_record,
                "home_logo_path": os.path.join(self.logo_dir, f"{home_team['team']['abbreviation']}.png"),
                "away_abbr": away_team["team"]["abbreviation"],
                "away_score": away_team.get("score", "0"),
                "away_record": away_record,
                "away_logo_path": os.path.join(self.logo_dir, f"{away_team['team']['abbreviation']}.png"),
                "game_time": game_time,
                "game_date": game_date,
                "id": game_event.get("id")
            }

            # Log game details for debugging
            self.logger.debug(f"[NHL] Extracted game details: {details['away_abbr']} vs {details['home_abbr']}")
            # Use .get() to avoid KeyError if optional keys are missing
            self.logger.debug(
                f"[NHL] Game status: is_final={details.get('is_final')}, "
                f"is_upcoming={details.get('is_upcoming')}, is_live={details.get('is_live')}"
            )

            # Validate logo files
            for team in ["home", "away"]:
                logo_path = details[f"{team}_logo_path"]
                if not os.path.isfile(logo_path):
                    logging.warning(f"[NHL] {team.title()} logo not found: {logo_path}")
                    details[f"{team}_logo_path"] = None
                else:
                    try:
                        with Image.open(logo_path) as img:
                            logging.debug(f"[NHL] {team.title()} logo is valid: {img.format}, size: {img.size}")
                    except Exception as e:
                        logging.error(f"[NHL] {team.title()} logo file exists but is not valid: {e}")
                        details[f"{team}_logo_path"] = None

            return details
        except Exception as e:
            logging.error(f"[NHL] Error extracting game details: {e}")
            return None

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the scorebug layout for the current game."""
        try:
            # Create a new black image for the main display
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            
            # Load logos once
            home_logo = self._load_and_resize_logo(game["home_abbr"])
            away_logo = self._load_and_resize_logo(game["away_abbr"])
            
            if not home_logo or not away_logo:
                self.logger.error("Failed to load one or both team logos")
                return

            # Create a single overlay for both logos
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))

            # Calculate vertical center line for alignment
            center_y = self.display_height // 2

            # Draw home team logo (far right, extending beyond screen)
            home_x = self.display_width - home_logo.width + 2
            home_y = center_y - (home_logo.height // 2)
            
            # Paste the home logo onto the overlay
            overlay.paste(home_logo, (home_x, home_y), home_logo)

            # Draw away team logo (far left, extending beyond screen)
            away_x = -2
            away_y = center_y - (away_logo.height // 2)
            
            # Paste the away logo onto the overlay
            overlay.paste(away_logo, (away_x, away_y), away_logo)

            # Composite the overlay with the main image
            main_img = Image.alpha_composite(main_img, overlay)

            # Convert to RGB for final display
            main_img = main_img.convert('RGB')
            draw = ImageDraw.Draw(main_img)

            # Check if this is an upcoming game
            is_upcoming = game.get("is_upcoming", False)
            
            if is_upcoming:
                # For upcoming games, show date and time stacked in the center
                game_date = game.get("game_date", "")
                game_time = game.get("game_time", "")
                
                # Show "Next Game" at the top
                status_text = "Next Game"
                status_width = draw.textlength(status_text, font=self.fonts['status'])
                status_x = (self.display_width - status_width) // 2
                status_y = 2
                self._draw_text_with_outline(draw, status_text, (status_x, status_y), self.fonts['status'])
                
                # Calculate position for the date text (centered horizontally, below "Next Game")
                date_width = draw.textlength(game_date, font=self.fonts['time'])
                date_x = (self.display_width - date_width) // 2
                date_y = center_y - 5  # Position in center
                self._draw_text_with_outline(draw, game_date, (date_x, date_y), self.fonts['time'])
                
                # Calculate position for the time text (centered horizontally, in center)
                time_width = draw.textlength(game_time, font=self.fonts['time'])
                time_x = (self.display_width - time_width) // 2
                time_y = date_y + 10  # Position below date
                self._draw_text_with_outline(draw, game_time, (time_x, time_y), self.fonts['time'])
            else:
                # For live/final games, show scores and period/time
                home_score = str(game.get("home_score", "0"))
                away_score = str(game.get("away_score", "0"))
                score_text = f"{away_score}-{home_score}"
                
                # Calculate position for the score text (centered at the bottom)
                score_width = draw.textlength(score_text, font=self.fonts['score'])
                score_x = (self.display_width - score_width) // 2
                score_y = self.display_height - 15
                self._draw_text_with_outline(draw, score_text, (score_x, score_y), self.fonts['score'])

                # Draw period and time or Final
                if game.get("is_final", False):
                    status_text = "Final"
                else:
                    period = game.get("period", 0)
                    clock = game.get("clock", "0:00")
                    
                    # Format period text
                    if period > 3:
                        period_text = "OT"
                    else:
                        period_text = f"{period}{'st' if period == 1 else 'nd' if period == 2 else 'rd'}"
                    
                    status_text = f"{period_text} {clock}"
                
                # Calculate position for the status text (centered at the top)
                status_width = draw.textlength(status_text, font=self.fonts['time'])
                status_x = (self.display_width - status_width) // 2
                status_y = 5
                self._draw_text_with_outline(draw, status_text, (status_x, status_y), self.fonts['time'])

            # Display odds if available
            if 'odds' in game:
                odds = game['odds']
                spread = odds.get('spread', {}).get('point', None)
                if spread is not None:
                    # Format spread text
                    spread_text = f"{spread:+.1f}" if spread > 0 else f"{spread:.1f}"
                    
                    # Choose color and position based on which team has the spread
                    if odds.get('spread', {}).get('team') == game['home_abbr']:
                        text_color = (255, 100, 100) # Reddish
                        spread_x = self.display_width - draw.textlength(spread_text, font=self.fonts['status']) - 2
                    else:
                        text_color = (100, 255, 100) # Greenish
                        spread_x = 2
                    
                    spread_y = 0
                    self._draw_text_with_outline(draw, spread_text, (spread_x, spread_y), self.fonts['status'], fill=text_color)

            # Draw records if enabled
            if self.show_records:
                try:
                    record_font = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
                except IOError:
                    record_font = ImageFont.load_default()
                
                away_record = game.get('away_record', '')
                home_record = game.get('home_record', '')
                
                record_bbox = draw.textbbox((0,0), "0-0", font=record_font)
                record_height = record_bbox[3] - record_bbox[1]
                record_y = self.display_height - record_height

                if away_record:
                    away_record_x = 2
                    self._draw_text_with_outline(draw, away_record, (away_record_x, record_y), record_font)

                if home_record:
                    home_record_bbox = draw.textbbox((0,0), home_record, font=record_font)
                    home_record_width = home_record_bbox[2] - home_record_bbox[0]
                    home_record_x = self.display_width - home_record_width - 2
                    self._draw_text_with_outline(draw, home_record, (home_record_x, record_y), record_font)

            # Display the image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display()

        except Exception as e:
            self.logger.error(f"Error displaying game: {e}", exc_info=True)

    def display(self, force_clear: bool = False) -> None:
        """Common display method for all NHL managers"""
        if not self.current_game:
            current_time = time.time()
            if not hasattr(self, '_last_warning_time'):
                self._last_warning_time = 0
            if current_time - self._last_warning_time > 300:  # 5 minutes cooldown
                self.logger.warning("[NHL] No game data available to display")
                self._last_warning_time = current_time
            return
            
        self._draw_scorebug_layout(self.current_game, force_clear)

class NHLLiveManager(BaseNHLManager):
    """Manager for live NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.update_interval = self.nhl_config.get("live_update_interval", 15)  # 15 seconds for live games
        self.no_data_interval = 300  # 5 minutes when no live games
        self.last_update = 0
        self.logger.info("Initialized NHL Live Manager")
        self.live_games = []  # List to store all live games
        self.current_game_index = 0  # Index to track which game to show
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = self.nhl_config.get("live_game_duration", 20)  # Display each live game for 20 seconds
        self.last_display_update = 0  # Track when we last updated the display
        self.last_log_time = 0
        self.log_interval = 300  # Only log status every 5 minutes
        
        # Initialize with test game only if test mode is enabled
        if self.test_mode:
            self.current_game = {
                "home_abbr": "TB",
                "away_abbr": "DAL",
                "home_score": "3",
                "away_score": "2",
                "period": 2,
                "clock": "12:34",
                "home_logo_path": os.path.join(self.logo_dir, "TB.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "game_time": "7:30 PM",
                "game_date": "Apr 17"
            }
            self.live_games = [self.current_game]
            logging.info("[NHL] Initialized NHLLiveManager with test game: TB vs DAL")
        else:
            logging.info("[NHL] Initialized NHLLiveManager in live mode")

    def update(self):
        """Update live game data."""
        if not self.is_enabled: return
        current_time = time.time()
        interval = self.no_data_interval if not self.live_games else self.update_interval

        if current_time - self.last_update >= interval:
            self.last_update = current_time
            
            if self.test_mode:
                # For testing, we'll just update the clock to show it's working
                if self.current_game:
                    minutes = int(self.current_game["clock"].split(":")[0])
                    seconds = int(self.current_game["clock"].split(":")[1])
                    seconds -= 1
                    if seconds < 0:
                        seconds = 59
                        minutes -= 1
                        if minutes < 0:
                            minutes = 19
                            if self.current_game["period"] < 3:
                                self.current_game["period"] += 1
                            else:
                                self.current_game["period"] = 1
                    self.current_game["clock"] = f"{minutes:02d}:{seconds:02d}"
                    # Always update display in test mode
                    self.display(force_clear=True)
            else:
                # Fetch live game data from ESPN API
                data = self._fetch_data()
                if data and "events" in data:
                    # Find all live games involving favorite teams
                    new_live_games = []
                    for event in data["events"]:
                        details = self._extract_game_details(event)
                        if details and details["is_live"]:
                            self._fetch_odds(details)
                            new_live_games.append(details)
                    
                    # Filter for favorite teams only if the config is set
                    if self.nhl_config.get("show_favorite_teams_only", False):
                        new_live_games = [game for game in new_live_games 
                                         if game['home_abbr'] in self.favorite_teams or 
                                            game['away_abbr'] in self.favorite_teams]
                    
                    # Only log if there's a change in games or enough time has passed
                    should_log = (
                        current_time - self.last_log_time >= self.log_interval or
                        len(new_live_games) != len(self.live_games) or
                        not self.live_games  # Log if we had no games before
                    )
                    
                    if should_log:
                        if new_live_games:
                            filter_text = "favorite teams" if self.nhl_config.get("show_favorite_teams_only", False) else "all teams"
                            self.logger.info(f"[NHL] Found {len(new_live_games)} live games involving {filter_text}")
                            for game in new_live_games:
                                self.logger.info(f"[NHL] Live game: {game['away_abbr']} vs {game['home_abbr']} - Period {game['period']}, {game['clock']}")
                        else:
                            filter_text = "favorite teams" if self.nhl_config.get("show_favorite_teams_only", False) else "criteria"
                            self.logger.info(f"[NHL] No live games found matching {filter_text}")
                        self.last_log_time = current_time
                    
                    if new_live_games:
                        # Update the current game with the latest data
                        for new_game in new_live_games:
                            if self.current_game and (
                                (new_game["home_abbr"] == self.current_game["home_abbr"] and 
                                 new_game["away_abbr"] == self.current_game["away_abbr"]) or
                                (new_game["home_abbr"] == self.current_game["away_abbr"] and 
                                 new_game["away_abbr"] == self.current_game["home_abbr"])
                            ):
                                self.current_game = new_game
                                break
                        
                        # Only update the games list if we have new games
                        if not self.live_games or set(game["away_abbr"] + game["home_abbr"] for game in new_live_games) != set(game["away_abbr"] + game["home_abbr"] for game in self.live_games):
                            self.live_games = new_live_games
                            # If we don't have a current game or it's not in the new list, start from the beginning
                            if not self.current_game or self.current_game not in self.live_games:
                                self.current_game_index = 0
                                self.current_game = self.live_games[0]
                                self.last_game_switch = current_time
                        
                        # Update display if data changed, limit rate
                        if current_time - self.last_display_update >= 1.0:
                            # self.display(force_clear=True) # REMOVED: DisplayController handles this
                            self.last_display_update = current_time
                        
                    else:
                        # No live games found
                        self.live_games = []
                        self.current_game = None
                
                # Check if it's time to switch games
                if len(self.live_games) > 1 and (current_time - self.last_game_switch) >= self.game_display_duration:
                    self.current_game_index = (self.current_game_index + 1) % len(self.live_games)
                    self.current_game = self.live_games[self.current_game_index]
                    self.last_game_switch = current_time
                    # self.display(force_clear=True) # REMOVED: DisplayController handles this
                    self.last_display_update = current_time # Track time for potential display update

    def display(self, force_clear=False):
        """Display live game information."""
        if not self.current_game:
            return
        super().display(force_clear)  # Call parent class's display method

class NHLRecentManager(BaseNHLManager):
    """Manager for recently completed NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.recent_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300  # 5 minutes
        self.recent_games_to_show = self.nhl_config.get("recent_games_to_show", 5)  # Number of most recent games to display
        self.last_game_switch = 0
        self.game_display_duration = 15  # Display each game for 15 seconds
        self.logger.info(f"Initialized NHLRecentManager with {len(self.favorite_teams)} favorite teams")
        
    def update(self):
        """Update recent games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
        
        self.last_update = current_time
            
        try:
            # Fetch data from ESPN API
            data = self._fetch_data()
            if not data or 'events' not in data:
                self.logger.warning("[NHL] No events found in ESPN API response")
                return
                
            events = data['events']
            self.logger.info(f"[NHL] Successfully fetched {len(events)} events from ESPN API")
            
            # Process games
            processed_games = []
            for event in events:
                game = self._extract_game_details(event)
                if game and game['is_final']:
                    # Fetch odds if enabled
                    self._fetch_odds(game)
                    processed_games.append(game)
            
            # Filter for favorite teams only if the config is set
            if self.nhl_config.get("show_favorite_teams_only", False):
                team_games = [game for game in processed_games
                         if game['home_abbr'] in self.favorite_teams or 
                            game['away_abbr'] in self.favorite_teams]
            else:
                team_games = processed_games
            
            # Sort games by start time, most recent first, then limit to recent_games_to_show
            team_games.sort(key=lambda x: x.get('start_time_utc') or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
            team_games = team_games[:self.recent_games_to_show]

            self.logger.info(f"[NHL] Found {len(team_games)} recent games for favorite teams (limited to {self.recent_games_to_show})")
            
            new_game_ids = {g['id'] for g in team_games}
            current_game_ids = {g['id'] for g in getattr(self, 'games_list', [])}

            if new_game_ids != current_game_ids:
                self.games_list = team_games
                self.current_game_index = 0
                self.current_game = self.games_list[0] if self.games_list else None
                self.last_game_switch = current_time
            elif self.games_list:
                self.current_game = self.games_list[self.current_game_index]

            if not self.games_list:
                self.current_game = None

        except Exception as e:
            self.logger.error(f"[NHL] Error updating recent games: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display recent games."""
        if not self.games_list:
            self.logger.info("[NHL] No recent games to display")
            return  # Skip display update entirely
            
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if len(self.games_list) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                # Move to next game
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True  # Force clear when switching games
            
            # Draw the scorebug layout
            self._draw_scorebug_layout(self.current_game, force_clear)
            
            # Update display
            self.display_manager.update_display()
            
        except Exception as e:
            self.logger.error(f"[NHL] Error displaying recent game: {e}", exc_info=True)

class NHLUpcomingManager(BaseNHLManager):
    """Manager for upcoming NHL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.upcoming_games = []
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300  # 5 minutes
        self.upcoming_games_to_show = self.nhl_config.get("upcoming_games_to_show", 5)  # Number of upcoming games to display
        self.last_log_time = 0
        self.log_interval = 300  # Only log status every 5 minutes
        self.last_warning_time = 0
        self.warning_cooldown = 300  # Only show warning every 5 minutes
        self.last_game_switch = 0  # Track when we last switched games
        self.game_display_duration = 15  # Display each game for 15 seconds
        self.logger.info(f"Initialized NHLUpcomingManager with {len(self.favorite_teams)} favorite teams")
        
    def update(self):
        """Update upcoming games data."""
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return
        
        self.last_update = current_time
            
        try:
            # Fetch data from ESPN API
            data = self._fetch_data()
            if not data or 'events' not in data:
                self.logger.warning("[NHL] No events found in ESPN API response")
                return
                
            events = data['events']
            self.logger.info(f"[NHL] Successfully fetched {len(events)} events from ESPN API")
            
            # Process games
            new_upcoming_games = []
            for event in events:
                game = self._extract_game_details(event)
                if game and game['is_upcoming']:
                    # Only fetch odds for games that will be displayed
                    if self.nhl_config.get("show_favorite_teams_only", False):
                        if not self.favorite_teams or (game['home_abbr'] not in self.favorite_teams and game['away_abbr'] not in self.favorite_teams):
                            continue
                    
                    self._fetch_odds(game)
                    new_upcoming_games.append(game)
            
            # Filter for favorite teams only if the config is set
            if self.nhl_config.get("show_favorite_teams_only", False):
                team_games = [game for game in new_upcoming_games 
                         if game['home_abbr'] in self.favorite_teams or 
                            game['away_abbr'] in self.favorite_teams]
            else:
                team_games = new_upcoming_games
            
            # Sort games by start time, soonest first, then limit to configured count
            team_games.sort(key=lambda x: x.get('start_time_utc') or datetime.max.replace(tzinfo=timezone.utc))
            team_games = team_games[:self.upcoming_games_to_show]

            # Only log if there's a change in games or enough time has passed
            should_log = (
                current_time - self.last_log_time >= self.log_interval or
                len(team_games) != len(self.upcoming_games) or
                not self.upcoming_games  # Log if we had no games before
            )
            
            if should_log:
                if team_games:
                    self.logger.info(f"[NHL] Found {len(team_games)} upcoming games for favorite teams (limited to {self.upcoming_games_to_show})")
                    for game in team_games:
                        self.logger.info(f"[NHL] Upcoming game: {game['away_abbr']} vs {game['home_abbr']} - {game['game_date']} {game['game_time']}")
                else:
                    self.logger.info("[NHL] No upcoming games found for favorite teams")
                    self.logger.debug(f"[NHL] Favorite teams: {self.favorite_teams}")
                self.last_log_time = current_time
            
            self.upcoming_games = team_games
            if self.upcoming_games:
                if not self.current_game or self.current_game['id'] not in {g['id'] for g in self.upcoming_games}:
                    self.current_game_index = 0
                    self.current_game = self.upcoming_games[0]
                    self.last_game_switch = current_time
            else:
                self.current_game = None
            
        except Exception as e:
            self.logger.error(f"[NHL] Error updating upcoming games: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display upcoming games."""
        if not self.upcoming_games:
            current_time = time.time()
            if current_time - self.last_warning_time > self.warning_cooldown:
                self.logger.info("[NHL] No upcoming games to display")
                self.last_warning_time = current_time
            return  # Skip display update entirely
            
        try:
            current_time = time.time()
            
            # Check if it's time to switch games
            if len(self.upcoming_games) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                # Move to next game
                self.current_game_index = (self.current_game_index + 1) % len(self.upcoming_games)
                self.current_game = self.upcoming_games[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True  # Force clear when switching games
            
            # Draw the scorebug layout
            self._draw_scorebug_layout(self.current_game, force_clear)
            
            # Update display
            self.display_manager.update_display()
            
        except Exception as e:
            self.logger.error(f"[NHL] Error displaying upcoming game: {e}", exc_info=True) 