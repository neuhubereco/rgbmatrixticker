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

# Constants
ESPN_NFL_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# Configure logging to match main configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s.%(msecs)03d - %(levelname)s:%(name)s:%(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)




class BaseNFLManager: # Renamed class
    """Base class for NFL managers with common functionality."""
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
        self.nfl_config = config.get("nfl_scoreboard", {}) # Changed config key
        self.is_enabled = self.nfl_config.get("enabled", False)
        self.show_odds = self.nfl_config.get("show_odds", False)
        self.test_mode = self.nfl_config.get("test_mode", False)
        self.logo_dir = self.nfl_config.get("logo_dir", "assets/sports/nfl_logos") # Changed logo dir
        self.update_interval = self.nfl_config.get("update_interval_seconds", 60)
        self.show_records = self.nfl_config.get('show_records', False)
        self.last_update = 0
        self.current_game = None
        self.fonts = self._load_fonts()
        self.favorite_teams = self.nfl_config.get("favorite_teams", [])

        # Check display modes to determine what data to fetch
        display_modes = self.nfl_config.get("display_modes", {})
        self.recent_enabled = display_modes.get("nfl_recent", False)
        self.upcoming_enabled = display_modes.get("nfl_upcoming", False)
        self.live_enabled = display_modes.get("nfl_live", False)

        self.logger.setLevel(logging.INFO)

        display_config = config.get("display", {})
        hardware_config = display_config.get("hardware", {})
        cols = hardware_config.get("cols", 64)
        chain = hardware_config.get("chain_length", 1)
        self.display_width = int(cols * chain)
        self.display_height = hardware_config.get("rows", 32)

        self._logo_cache = {}

        # Set up session with retry logic
        self.session = requests.Session()
        self.session.mount('http://', requests.adapters.HTTPAdapter(max_retries=3))
        self.session.mount('https://', requests.adapters.HTTPAdapter(max_retries=3))
        
        # Set up headers for ESPN API
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        self.logger.info(f"Initialized NFL manager with display dimensions: {self.display_width}x{self.display_height}")
        self.logger.info(f"Logo directory: {self.logo_dir}")
        self.logger.info(f"Display modes - Recent: {self.recent_enabled}, Upcoming: {self.upcoming_enabled}, Live: {self.live_enabled}")

    def _get_timezone(self):
        try:
            return pytz.timezone(self.config_manager.get_timezone())
        except pytz.UnknownTimeZoneError:
            return pytz.utc

    def _should_log(self, warning_type: str, cooldown: int = 60) -> bool:
        """Check if we should log a warning based on cooldown period."""
        current_time = time.time()
        if current_time - self._last_warning_time > cooldown:
            self._last_warning_time = current_time
            return True
        return False

    def _fetch_odds(self, game: Dict) -> None:
        """Fetch odds for a specific game if conditions are met."""
        # Check if odds should be shown for this sport
        if not self.show_odds:
            return

        # Check if we should only fetch for favorite teams
        is_favorites_only = self.nfl_config.get("show_favorite_teams_only", False)
        if is_favorites_only:
            home_abbr = game.get('home_abbr')
            away_abbr = game.get('away_abbr')
            if not (home_abbr in self.favorite_teams or away_abbr in self.favorite_teams):
                self.logger.debug(f"Skipping odds fetch for non-favorite game in favorites-only mode: {away_abbr}@{home_abbr}")
                return

        self.logger.debug(f"Proceeding with odds fetch for game: {game.get('id', 'N/A')}")
        
        # Fetch odds using OddsManager (ESPN API)
        try:
            # Determine update interval based on game state
            is_live = game.get('status', '').lower() == 'in'
            update_interval = self.nfl_config.get("live_odds_update_interval", 60) if is_live \
                else self.nfl_config.get("odds_update_interval", 3600)

            odds_data = self.odds_manager.get_odds(
                sport="football",
                league="nfl",
                event_id=game['id'],
                update_interval_seconds=update_interval
            )
            
            if odds_data:
                game['odds'] = odds_data
                self.logger.debug(f"Successfully fetched and attached odds for game {game['id']}")
            else:
                self.logger.debug(f"No odds data returned for game {game['id']}")

        except Exception as e:
            self.logger.error(f"Error fetching odds for game {game.get('id', 'N/A')}: {e}")
            
    def _fetch_nfl_api_data(self, use_cache: bool = True) -> Optional[Dict]:
        """
        Fetches the full season schedule for NFL, caches it, and then filters
        for relevant games based on the current configuration.
        """
        now = datetime.now(pytz.utc)
        current_year = now.year
        cache_key = f"nfl_schedule_{current_year}"

        if use_cache:
            cached_data = self.cache_manager.get(cache_key)
            if cached_data:
                self.logger.info(f"[NFL] Using cached schedule for {current_year}")
                return {'events': cached_data}
        
        self.logger.info(f"[NFL] Fetching full {current_year} season schedule from ESPN API (cache_enabled={use_cache})...")
        try:
            url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={current_year}"
            response = self.session.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()
            data = response.json()
            events = data.get('events', [])
            
            if use_cache:
                self.cache_manager.set(cache_key, events)
            
            self.logger.info(f"[NFL] Successfully fetched {len(events)} events for the {current_year} season.")
            return {'events': events}
        except requests.exceptions.RequestException as e:
            self.logger.error(f"[NFL] API error fetching full schedule: {e}")
            return None

    def _fetch_data(self, date_str: str = None) -> Optional[Dict]:
        """Fetch data using shared data mechanism or direct fetch for live."""
        if isinstance(self, NFLLiveManager):
            return self._fetch_nfl_api_data(use_cache=False)
        else:
            return self._fetch_nfl_api_data(use_cache=True)

    def _load_fonts(self):
        """Load fonts used by the scoreboard."""
        fonts = {}
        try:
            fonts['score'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 10)
            fonts['time'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['team'] = ImageFont.truetype("assets/fonts/PressStart2P-Regular.ttf", 8)
            fonts['status'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6) # Using 4x6 for status
            fonts['detail'] = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6) # Added detail font
            logging.info("[NFL] Successfully loaded fonts")
        except IOError:
            logging.warning("[NFL] Fonts not found, using default PIL font.")
            fonts['score'] = ImageFont.load_default()
            fonts['time'] = ImageFont.load_default()
            fonts['team'] = ImageFont.load_default()
            fonts['status'] = ImageFont.load_default()
            fonts['detail'] = ImageFont.load_default()
        return fonts

    def _draw_dynamic_odds(self, draw: ImageDraw.Draw, odds: Dict[str, Any], width: int, height: int) -> None:
        """Draw odds with dynamic positioning - only show negative spread and position O/U based on favored team."""
        home_team_odds = odds.get('home_team_odds', {})
        away_team_odds = odds.get('away_team_odds', {})
        home_spread = home_team_odds.get('spread_odds')
        away_spread = away_team_odds.get('spread_odds')

        # Get top-level spread as fallback
        top_level_spread = odds.get('spread')
        
        # If we have a top-level spread and the individual spreads are None or 0, use the top-level
        if top_level_spread is not None:
            if home_spread is None or home_spread == 0.0:
                home_spread = top_level_spread
            if away_spread is None:
                away_spread = -top_level_spread

        # Determine which team is favored (has negative spread)
        home_favored = home_spread is not None and home_spread < 0
        away_favored = away_spread is not None and away_spread < 0
        
        # Only show the negative spread (favored team)
        favored_spread = None
        favored_side = None
        
        if home_favored:
            favored_spread = home_spread
            favored_side = 'home'
            self.logger.debug(f"Home team favored with spread: {favored_spread}")
        elif away_favored:
            favored_spread = away_spread
            favored_side = 'away'
            self.logger.debug(f"Away team favored with spread: {favored_spread}")
        else:
            self.logger.debug("No clear favorite - spreads: home={home_spread}, away={away_spread}")
        
        # Show over/under on the opposite side of the favored team
        over_under = odds.get('over_under')
        if over_under is not None:
            ou_text = f"O/U: {over_under}"
            font = self.fonts['detail']  # Use detail font for odds
            ou_width = draw.textlength(ou_text, font=font)
            
            if favored_side == 'home':
                # Home team is favored, show O/U on left side (opposite of spread)
                ou_x = 0  # Top left
                ou_y = 0
                self.logger.debug(f"Showing O/U '{ou_text}' on left side (home favored)")
            elif favored_side == 'away':
                # Away team is favored, show O/U on right side (opposite of spread)
                ou_x = width - ou_width  # Top right
                ou_y = 0
                self.logger.debug(f"Showing O/U '{ou_text}' on right side (away favored)")
            else:
                # No clear favorite, show O/U in center
                ou_x = (width - ou_width) // 2
                ou_y = 0
                self.logger.debug(f"Showing O/U '{ou_text}' in center (no clear favorite)")
            
            self._draw_text_with_outline(draw, ou_text, (ou_x, ou_y), font, fill=(0, 255, 0))

    def _draw_text_with_outline(self, draw, text, position, font, fill=(255, 255, 255), outline_color=(0, 0, 0)):
        """Draw text with a black outline for better readability."""
        x, y = position
        for dx, dy in [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]:
            draw.text((x + dx, y + dy), text, font=font, fill=outline_color)
        draw.text((x, y), text, font=font, fill=fill)

    def _load_and_resize_logo(self, team_abbrev: str) -> Optional[Image.Image]:
        """Load and resize a team logo, with caching."""
        if team_abbrev in self._logo_cache:
            return self._logo_cache[team_abbrev]

        logo_path = os.path.join(self.logo_dir, f"{team_abbrev}.png")
        self.logger.debug(f"Logo path: {logo_path}")

        try:
            # Create placeholder if logo doesn't exist (useful for testing)
            if not os.path.exists(logo_path):
                self.logger.warning(f"Logo not found for {team_abbrev} at {logo_path}. Creating placeholder.")
                os.makedirs(os.path.dirname(logo_path), exist_ok=True)
                logo = Image.new('RGBA', (32, 32), (200, 200, 200, 255)) # Gray placeholder
                draw = ImageDraw.Draw(logo)
                draw.text((2, 10), team_abbrev, fill=(0, 0, 0, 255))
                logo.save(logo_path)
                self.logger.info(f"Created placeholder logo at {logo_path}")

            logo = Image.open(logo_path)
            if logo.mode != 'RGBA':
                logo = logo.convert('RGBA')

            max_width = int(self.display_width * 1.5)
            max_height = int(self.display_height * 1.5)
            logo.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
            self._logo_cache[team_abbrev] = logo
            return logo

        except Exception as e:
            self.logger.error(f"Error loading logo for {team_abbrev}: {e}", exc_info=True)
            return None

    def _extract_game_details(self, game_event: Dict) -> Optional[Dict]:
        """Extract relevant game details from ESPN NFL API response."""
        # --- THIS METHOD NEEDS SIGNIFICANT ADAPTATION FOR NFL API ---
        if not game_event: return None

        try:
            competition = game_event["competitions"][0]
            status = competition["status"]
            competitors = competition["competitors"]
            game_date_str = game_event["date"]

            start_time_utc = None
            try:
                start_time_utc = datetime.fromisoformat(game_date_str.replace("Z", "+00:00"))
            except ValueError:
                logging.warning(f"[NFL] Could not parse game date: {game_date_str}")

            home_team = next((c for c in competitors if c.get("homeAway") == "home"), None)
            away_team = next((c for c in competitors if c.get("homeAway") == "away"), None)

            if not home_team or not away_team:
                 self.logger.warning(f"[NFL] Could not find home or away team in event: {game_event.get('id')}")
                 return None

            home_abbr = home_team["team"]["abbreviation"]
            away_abbr = away_team["team"]["abbreviation"]
            home_record = home_team.get('records', [{}])[0].get('summary', '') if home_team.get('records') else ''
            away_record = away_team.get('records', [{}])[0].get('summary', '') if away_team.get('records') else ''
            
            # Don't show "0-0" records - set to blank instead
            if home_record == "0-0":
                home_record = ''
            if away_record == "0-0":
                away_record = ''

            # Remove early filtering - let individual managers handle their own filtering
            # This allows shared data to contain all games, and each manager can filter as needed

            game_time = ""
            game_date = ""
            if start_time_utc:
                local_time = start_time_utc.astimezone(self._get_timezone())
                game_time = local_time.strftime("%I:%M%p").lstrip('0')
                
                # Check date format from config
                use_short_date_format = self.config.get('display', {}).get('use_short_date_format', False)
                if use_short_date_format:
                    game_date = local_time.strftime("%-m/%-d")
                else:
                    game_date = self.display_manager.format_date_with_ordinal(local_time)

            # --- NFL Specific Details ---
            situation = competition.get("situation")
            down_distance_text = ""
            possession_indicator = None # Default to None
            if situation and status["type"]["state"] == "in":
                down = situation.get("down")
                distance = situation.get("distance")
                if down and distance is not None:
                    down_str = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(down, f"{down}th")
                    dist_str = f"& {distance}" if distance > 0 else "& Goal"
                    down_distance_text = f"{down_str} {dist_str}"
                elif situation.get("isRedZone"):
                     down_distance_text = "Red Zone" # Simplified if down/distance not present but in redzone
                
                # Determine possession based on team ID
                possession_team_id = situation.get("possession")
                if possession_team_id:
                    if possession_team_id == home_team.get("id"):
                        possession_indicator = "home"
                    elif possession_team_id == away_team.get("id"):
                        possession_indicator = "away"


            # Format period/quarter
            period = status.get("period", 0)
            period_text = ""
            if status["type"]["state"] == "in":
                 if period == 0: period_text = "Start" # Before kickoff
                 elif period == 1: period_text = "Q1"
                 elif period == 2: period_text = "Q2"
                 elif period == 3: period_text = "Q3" # Fixed: period 3 is 3rd quarter, not halftime
                 elif period == 4: period_text = "Q4"
                 elif period > 4: period_text = "OT" # OT starts after Q4
            elif status["type"]["state"] == "halftime" or status["type"]["name"] == "STATUS_HALFTIME": # Check explicit halftime state
                period_text = "HALF"
            elif status["type"]["state"] == "post":
                 if period > 4 : period_text = "Final/OT"
                 else: period_text = "Final"
            elif status["type"]["state"] == "pre":
                period_text = game_time # Show time for upcoming

            # Timeouts (assuming max 3 per half, not carried over well in standard API)
            # API often provides 'timeouts' directly under team, but reset logic is tricky
            # We might need to simplify this or just use a fixed display if API is unreliable
            home_timeouts = home_team.get("timeouts", 3) # Default to 3 if not specified
            away_timeouts = away_team.get("timeouts", 3) # Default to 3 if not specified


            details = {
                "id": game_event.get("id"),
                "start_time_utc": start_time_utc,
                "status_text": status["type"]["shortDetail"], # e.g., "Final", "7:30 PM", "Q1 12:34"
                "period": period,
                "period_text": period_text, # Formatted quarter/status
                "clock": status.get("displayClock", "0:00"),
                "is_live": status["type"]["state"] == "in",
                "is_final": status["type"]["state"] == "post",
                "is_upcoming": status["type"]["state"] == "pre",
                "is_halftime": status["type"]["state"] == "halftime" or status["type"]["name"] == "STATUS_HALFTIME", # Added halftime check
                "home_abbr": home_abbr,
                "home_score": home_team.get("score", "0"),
                "home_record": home_record,
                "home_logo_path": os.path.join(self.logo_dir, f"{home_abbr}.png"),
                "home_timeouts": home_timeouts,
                "away_abbr": away_abbr,
                "away_score": away_team.get("score", "0"),
                "away_record": away_record,
                "away_logo_path": os.path.join(self.logo_dir, f"{away_abbr}.png"),
                "away_timeouts": away_timeouts,
                "game_time": game_time,
                "game_date": game_date,
                "down_distance_text": down_distance_text, # Added Down/Distance
                "possession": situation.get("possession") if situation else None, # ID of team with possession
                "possession_indicator": possession_indicator, # Added for easy home/away check
            }

            # Basic validation (can be expanded)
            if not details['home_abbr'] or not details['away_abbr']:
                 self.logger.warning(f"[NFL] Missing team abbreviation in event: {details['id']}")
                 return None

            self.logger.debug(f"[NFL] Extracted: {details['away_abbr']}@{details['home_abbr']}, Status: {status['type']['name']}, Live: {details['is_live']}, Final: {details['is_final']}, Upcoming: {details['is_upcoming']}")

            # Logo validation (optional but good practice)
            for team in ["home", "away"]:
                logo_path = details[f"{team}_logo_path"]
                # No need to check file existence here, _load_and_resize_logo handles it

            return details
        except Exception as e:
            # Log the problematic event structure if possible
            logging.error(f"[NFL] Error extracting game details: {e} from event: {game_event.get('id')}", exc_info=True)
            return None

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Placeholder draw method - subclasses should override."""
        # This base method will be simple, subclasses provide specifics
        try:
            img = Image.new('RGB', (self.display_width, self.display_height), (0, 0, 0))
            draw = ImageDraw.Draw(img)
            status = game.get("status_text", "N/A")
            self._draw_text_with_outline(draw, status, (2, 2), self.fonts['status'])
            self.display_manager.image.paste(img, (0, 0))
            # Don't call update_display here, let subclasses handle it after drawing
        except Exception as e:
            self.logger.error(f"Error in base _draw_scorebug_layout: {e}", exc_info=True)


    def display(self, force_clear: bool = False) -> None:
        """Common display method for all NFL managers"""
        if not self.is_enabled: # Check if module is enabled
             return

        if not self.current_game:
            current_time = time.time()
            if not hasattr(self, '_last_warning_time'):
                self._last_warning_time = 0
            if current_time - getattr(self, '_last_warning_time', 0) > 300:
                self.logger.warning(f"[NFL] No game data available to display in {self.__class__.__name__}")
                setattr(self, '_last_warning_time', current_time)
            return

        try:
            self._draw_scorebug_layout(self.current_game, force_clear)
            # display_manager.update_display() should be called within subclass draw methods
            # or after calling display() in the main loop. Let's keep it out of the base display.
        except Exception as e:
             self.logger.error(f"[NFL] Error during display call in {self.__class__.__name__}: {e}", exc_info=True)


class NFLLiveManager(BaseNFLManager): # Renamed class
    """Manager for live NFL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.update_interval = self.nfl_config.get("live_update_interval", 15)
        self.no_data_interval = 300
        self.last_update = 0
        self.logger.info("Initialized NFL Live Manager")
        self.live_games = []
        self.current_game_index = 0
        self.last_game_switch = 0
        self.game_display_duration = self.nfl_config.get("live_game_duration", 20)
        self.last_display_update = 0
        self.last_log_time = 0
        self.log_interval = 300

        if self.test_mode:
            # More detailed test game for NFL
            self.current_game = {
                "id": "test001",
                "home_abbr": "TB", "away_abbr": "DAL",
                "home_score": "21", "away_score": "17",
                "period": 4, "period_text": "Q4", "clock": "02:35",
                "down_distance_text": "1st & 10", 
                "possession": "TB", # Placeholder ID for home team
                "possession_indicator": "home", # Explicitly set for test
                "home_timeouts": 2, "away_timeouts": 3,
                "home_logo_path": os.path.join(self.logo_dir, "TB.png"),
                "away_logo_path": os.path.join(self.logo_dir, "DAL.png"),
                "is_live": True, "is_final": False, "is_upcoming": False, "is_halftime": False,
                "status_text": "Q4 02:35"
            }
            self.live_games = [self.current_game]
            logging.info("[NFL] Initialized NFLLiveManager with test game: BUF vs KC")
        else:
            logging.info("[NFL] Initialized NFLLiveManager in live mode")

    def update(self):
        """Update live game data."""
        if not self.is_enabled: return
        current_time = time.time()
        interval = self.no_data_interval if not self.live_games and not self.test_mode else self.update_interval

        if current_time - self.last_update >= interval:
            self.last_update = current_time

            if self.test_mode:
                # Simulate clock running down in test mode
                if self.current_game and self.current_game["is_live"]:
                    try:
                        minutes, seconds = map(int, self.current_game["clock"].split(':'))
                        seconds -= 1
                        if seconds < 0:
                            seconds = 59
                            minutes -= 1
                            if minutes < 0:
                                # Simulate end of quarter/game
                                if self.current_game["period"] < 5: # Assuming 5 is Q4 end
                                    self.current_game["period"] += 1
                                    # Update period_text based on new period
                                    if self.current_game["period"] == 3: self.current_game["period_text"] = "HALF"
                                    elif self.current_game["period"] == 5: self.current_game["period_text"] = "Q4"
                                    # Reset clock for next quarter (e.g., 15:00)
                                    minutes, seconds = 15, 0
                                else:
                                    # Simulate game end
                                    self.current_game["is_live"] = False
                                    self.current_game["is_final"] = True
                                    self.current_game["period_text"] = "Final"
                                    minutes, seconds = 0, 0
                        self.current_game["clock"] = f"{minutes:02d}:{seconds:02d}"
                        # Simulate down change occasionally
                        if seconds % 15 == 0:
                             self.current_game["down_distance_text"] = f"{['1st','2nd','3rd','4th'][seconds % 4]} & {seconds % 10 + 1}"
                        self.current_game["status_text"] = f"{self.current_game['period_text']} {self.current_game['clock']}"

                    except ValueError:
                        self.logger.warning("[NFL] Test mode: Could not parse clock")
            else:
                # Fetch live game data
                data = self._fetch_data()
                new_live_games = []
                if data and "events" in data:
                    events = data["events"]

                    # --- Optimization: Filter for favorite teams before extracting details/odds ---
                    if self.nfl_config.get("show_favorite_teams_only", False):
                        filtered_events = []
                        for event in events:
                            try:
                                competitors = event["competitions"][0]["competitors"]
                                if any(c["team"]["abbreviation"] in self.favorite_teams for c in competitors):
                                    filtered_events.append(event)
                            except (KeyError, IndexError):
                                continue # Skip event if data structure is unexpected
                        events = filtered_events
                        self.logger.info(f"[NFL Live] Filtered to {len(events)} events for favorite teams.")


                    for event in events:
                        details = self._extract_game_details(event)
                        if details and (details["is_live"] or details["is_halftime"]): # Include halftime as 'live' display
                            # Only apply favorite team filtering if show_favorite_teams_only is true
                            if not self.nfl_config.get("show_favorite_teams_only", False) or (
                                details["home_abbr"] in self.favorite_teams or
                                details["away_abbr"] in self.favorite_teams
                            ):
                                # Fetch odds if enabled
                                self._fetch_odds(details)
                                new_live_games.append(details)

                    # Log changes or periodically
                    should_log = (
                        current_time - self.last_log_time >= self.log_interval or
                        len(new_live_games) != len(self.live_games) or
                        any(g1['id'] != g2.get('id') for g1, g2 in zip(self.live_games, new_live_games)) or # Check if game IDs changed
                        (not self.live_games and new_live_games) # Log if games appeared
                    )

                    if should_log:
                        if new_live_games:
                            filter_text = "favorite teams" if self.nfl_config.get("show_favorite_teams_only", False) else "all teams"
                            self.logger.info(f"[NFL] Found {len(new_live_games)} live/halftime games for {filter_text}.")
                            for game in new_live_games:
                                self.logger.info(f"  - {game['away_abbr']}@{game['home_abbr']} ({game.get('status_text', 'N/A')})")
                        else:
                            filter_text = "favorite teams" if self.nfl_config.get("show_favorite_teams_only", False) else "criteria"
                            self.logger.info(f"[NFL] No live/halftime games found for {filter_text}.")
                        self.last_log_time = current_time


                    # Update game list and current game
                    if new_live_games:
                        # Check if the games themselves changed, not just scores/time
                        new_game_ids = {g['id'] for g in new_live_games}
                        current_game_ids = {g['id'] for g in self.live_games}

                        if new_game_ids != current_game_ids:
                            self.live_games = sorted(new_live_games, key=lambda g: g.get('start_time_utc') or datetime.now(self._get_timezone())) # Sort by start time
                            # Reset index if current game is gone or list is new
                            if not self.current_game or self.current_game['id'] not in new_game_ids:
                                self.current_game_index = 0
                                self.current_game = self.live_games[0] if self.live_games else None
                                self.last_game_switch = current_time
                            else:
                                # Find current game's new index if it still exists
                                try:
                                     self.current_game_index = next(i for i, g in enumerate(self.live_games) if g['id'] == self.current_game['id'])
                                     self.current_game = self.live_games[self.current_game_index] # Update current_game with fresh data
                                except StopIteration: # Should not happen if check above passed, but safety first
                                     self.current_game_index = 0
                                     self.current_game = self.live_games[0]
                                     self.last_game_switch = current_time

                        else:
                             # Just update the data for the existing games
                             temp_game_dict = {g['id']: g for g in new_live_games}
                             self.live_games = [temp_game_dict.get(g['id'], g) for g in self.live_games] # Update in place
                             if self.current_game:
                                  self.current_game = temp_game_dict.get(self.current_game['id'], self.current_game)

                        # Display update handled by main loop based on interval

                    else:
                        # No live games found
                        if self.live_games: # Were there games before?
                             self.logger.info("[NFL] Live games previously showing have ended or are no longer live.")
                        self.live_games = []
                        self.current_game = None
                        self.current_game_index = 0

                else:
                    # Error fetching data or no events
                     if self.live_games: # Were there games before?
                         self.logger.warning("[NFL] Could not fetch update; keeping existing live game data for now.")
                     else:
                         self.logger.warning("[NFL] Could not fetch data and no existing live games.")
                         self.current_game = None # Clear current game if fetch fails and no games were active

            # Handle game switching (outside test mode check)
            if not self.test_mode and len(self.live_games) > 1 and (current_time - self.last_game_switch) >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.live_games)
                self.current_game = self.live_games[self.current_game_index]
                self.last_game_switch = current_time
                self.logger.info(f"[NFL] Switched live view to: {self.current_game['away_abbr']}@{self.current_game['home_abbr']}")
                # Force display update via flag or direct call if needed, but usually let main loop handle

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the detailed scorebug layout for a live NFL game."""
        try:
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay) # Draw text elements on overlay first

            home_logo = self._load_and_resize_logo(game["home_abbr"])
            away_logo = self._load_and_resize_logo(game["away_abbr"])

            if not home_logo or not away_logo:
                self.logger.error(f"[NFL] Failed to load logos for live game: {game.get('id')}")
                # Draw placeholder text if logos fail
                draw_final = ImageDraw.Draw(main_img.convert('RGB'))
                self._draw_text_with_outline(draw_final, "Logo Error", (5,5), self.fonts['status'])
                self.display_manager.image.paste(main_img.convert('RGB'), (0, 0))
                self.display_manager.update_display()
                return

            center_y = self.display_height // 2

            # Draw logos (shifted slightly more inward than NHL perhaps)
            home_x = self.display_width - home_logo.width + 10 #adjusted from 18 # Adjust position as needed
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)

            away_x = -10 #adjusted from 18 # Adjust position as needed
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)

            # --- Draw Text Elements on Overlay ---
            # Scores (centered, slightly above bottom)
            home_score = str(game.get("home_score", "0"))
            away_score = str(game.get("away_score", "0"))
            score_text = f"{away_score}-{home_score}"
            score_width = draw_overlay.textlength(score_text, font=self.fonts['score'])
            score_x = (self.display_width - score_width) // 2
            score_y = (self.display_height // 2) - 3 #centered #from 14 # Position score higher
            self._draw_text_with_outline(draw_overlay, score_text, (score_x, score_y), self.fonts['score'])

            # Period/Quarter and Clock (Top center)
            period_clock_text = f"{game.get('period_text', '')} {game.get('clock', '')}".strip()
            if game.get("is_halftime"): period_clock_text = "Halftime" # Override for halftime

            status_width = draw_overlay.textlength(period_clock_text, font=self.fonts['time'])
            status_x = (self.display_width - status_width) // 2
            status_y = 1 # Position at top
            self._draw_text_with_outline(draw_overlay, period_clock_text, (status_x, status_y), self.fonts['time'])

            # Down & Distance (Below Period/Clock)
            down_distance = game.get("down_distance_text", "")
            if down_distance and game.get("is_live"): # Only show if live and available
                dd_width = draw_overlay.textlength(down_distance, font=self.fonts['detail'])
                dd_x = (self.display_width - dd_width) // 2
                dd_y = (self.display_height)- 7 # Top of D&D text
                self._draw_text_with_outline(draw_overlay, down_distance, (dd_x, dd_y), self.fonts['detail'], fill=(200, 200, 0)) # Yellowish text

                # Possession Indicator (small football icon)
                possession = game.get("possession_indicator")
                if possession: # Only draw if possession is known
                    ball_radius_x = 3  # Wider for football shape
                    ball_radius_y = 2  # Shorter for football shape
                    ball_color = (139, 69, 19) # Brown color for the football
                    lace_color = (255, 255, 255) # White for laces

                    # Approximate height of the detail font (4x6 font at size 6 is roughly 6px tall)
                    detail_font_height_approx = 6
                    ball_y_center = dd_y + (detail_font_height_approx // 2) # Center ball vertically with D&D text

                    possession_ball_padding = 3 # Pixels between D&D text and ball

                    if possession == "away":
                        # Position ball to the left of D&D text
                        ball_x_center = dd_x - possession_ball_padding - ball_radius_x
                    elif possession == "home":
                        # Position ball to the right of D&D text
                        ball_x_center = dd_x + dd_width + possession_ball_padding + ball_radius_x
                    else:
                        ball_x_center = 0 # Should not happen / no indicator

                    if ball_x_center > 0: # Draw if position is valid
                        # Draw the football shape (ellipse)
                        draw_overlay.ellipse(
                            (ball_x_center - ball_radius_x, ball_y_center - ball_radius_y,  # x0, y0
                             ball_x_center + ball_radius_x, ball_y_center + ball_radius_y), # x1, y1
                            fill=ball_color, outline=(0,0,0)
                        )
                        # Draw a simple horizontal lace
                        draw_overlay.line(
                            (ball_x_center - 1, ball_y_center, ball_x_center + 1, ball_y_center),
                            fill=lace_color, width=1
                        )

            # Timeouts (Bottom corners) - 3 small bars per team
            timeout_bar_width = 4
            timeout_bar_height = 2
            timeout_spacing = 1
            timeout_y = self.display_height - timeout_bar_height - 1 # Bottom edge

            # Away Timeouts (Bottom Left)
            away_timeouts_remaining = game.get("away_timeouts", 0)
            for i in range(3):
                to_x = 2 + i * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < away_timeouts_remaining else (80, 80, 80) # White if available, gray if used
                draw_overlay.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], fill=color, outline=(0,0,0))

             # Home Timeouts (Bottom Right)
            home_timeouts_remaining = game.get("home_timeouts", 0)
            for i in range(3):
                to_x = self.display_width - 2 - timeout_bar_width - (2-i) * (timeout_bar_width + timeout_spacing)
                color = (255, 255, 255) if i < home_timeouts_remaining else (80, 80, 80) # White if available, gray if used
                draw_overlay.rectangle([to_x, timeout_y, to_x + timeout_bar_width, timeout_y + timeout_bar_height], fill=color, outline=(0,0,0))

            # Draw odds if available
            if 'odds' in game and game['odds']:
                self._draw_dynamic_odds(draw_overlay, game['odds'], self.display_width, self.display_height)

            # Composite the text overlay onto the main image
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert('RGB') # Convert for display

            # Display the final image
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display() # Update display here for live

        except Exception as e:
            self.logger.error(f"Error displaying live NFL game: {e}", exc_info=True)

    # Inherits display() method from BaseNFLManager, which calls the overridden _draw_scorebug_layout


class NFLRecentManager(BaseNFLManager): # Renamed class
    """Manager for recently completed NFL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.recent_games = [] # Store all fetched recent games initially
        self.games_list = [] # Filtered list for display (favorite teams)
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300 # Check for recent games every 5 mins
        self.last_game_switch = 0
        self.game_display_duration = 15 # Display each recent game for 15 seconds
        self.logger.info(f"Initialized NFLRecentManager with {len(self.favorite_teams)} favorite teams")

    def update(self):
        """Update recent games data."""
        if not self.is_enabled: return
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        self.last_update = current_time # Update time even if fetch fails
        try:
            data = self._fetch_data() # Uses shared cache
            if not data or 'events' not in data:
                self.logger.warning("[NFL Recent] No events found in shared data.")
                if not self.games_list: self.current_game = None # Clear display if no games were showing
                return

            events = data['events']

            # --- Optimization: Filter for favorite teams before extracting details/odds ---
            if self.nfl_config.get("show_favorite_teams_only", False):
                filtered_events = []
                for event in events:
                    try:
                        competitors = event["competitions"][0]["competitors"]
                        if any(c["team"]["abbreviation"] in self.favorite_teams for c in competitors):
                            filtered_events.append(event)
                    except (KeyError, IndexError):
                        continue # Skip event if data structure is unexpected
                events = filtered_events
                self.logger.info(f"[NFL Recent] Filtered to {len(events)} events for favorite teams.")

            # Process games and filter for final & within window & favorite teams
            processed_games = []
            for event in events:
                game = self._extract_game_details(event)
                # Filter criteria: must be final
                if game and game['is_final']:
                    # Fetch odds if enabled
                    self._fetch_odds(game)
                    processed_games.append(game)

            # Filter for favorite teams only if the config is set
            if self.nfl_config.get("show_favorite_teams_only", False):
                 team_games = [game for game in processed_games
                              if game['home_abbr'] in self.favorite_teams or
                                 game['away_abbr'] in self.favorite_teams]
            else:
                 team_games = processed_games # Show all recent games if no favorites defined

            # Sort by game time, most recent first
            team_games.sort(key=lambda g: g.get('start_time_utc') or datetime.min.replace(tzinfo=self._get_timezone()), reverse=True)
            
            # Limit to the specified number of recent games (default 5)
            recent_games_to_show = self.nfl_config.get("recent_games_to_show", 5)
            team_games = team_games[:recent_games_to_show]

            # Check if the list of games to display has changed
            new_game_ids = {g['id'] for g in team_games}
            current_game_ids = {g['id'] for g in self.games_list}

            if new_game_ids != current_game_ids:
                self.logger.info(f"[NFL Recent] Found {len(team_games)} final games within window for display.")
                self.games_list = team_games
                # Reset index if list changed or current game removed
                if not self.current_game or not self.games_list or self.current_game['id'] not in new_game_ids:
                     self.current_game_index = 0
                     self.current_game = self.games_list[0] if self.games_list else None
                     self.last_game_switch = current_time # Reset switch timer
                else:
                     # Try to maintain position if possible
                     try:
                          self.current_game_index = next(i for i, g in enumerate(self.games_list) if g['id'] == self.current_game['id'])
                          self.current_game = self.games_list[self.current_game_index] # Update data just in case
                     except StopIteration:
                          self.current_game_index = 0
                          self.current_game = self.games_list[0]
                          self.last_game_switch = current_time

            elif self.games_list:
                 # List content is same, just update data for current game
                 self.current_game = self.games_list[self.current_game_index]


            if not self.games_list:
                 self.logger.info("[NFL Recent] No relevant recent games found to display.")
                 self.current_game = None # Ensure display clears if no games

        except Exception as e:
            self.logger.error(f"[NFL Recent] Error updating recent games: {e}", exc_info=True)
            # Don't clear current game on error, keep showing last known state
            # self.current_game = None # Decide if we want to clear display on error

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the layout for a recently completed NFL game."""
        try:
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            home_logo = self._load_and_resize_logo(game["home_abbr"])
            away_logo = self._load_and_resize_logo(game["away_abbr"])

            if not home_logo or not away_logo:
                self.logger.error(f"[NFL Recent] Failed to load logos for game: {game.get('id')}")
                # Draw placeholder text if logos fail (similar to live)
                draw_final = ImageDraw.Draw(main_img.convert('RGB'))
                self._draw_text_with_outline(draw_final, "Logo Error", (5,5), self.fonts['status'])
                self.display_manager.image.paste(main_img.convert('RGB'), (0, 0))
                self.display_manager.update_display()
                return

            center_y = self.display_height // 2

            # MLB-style logo positioning (closer to edges)
            home_x = self.display_width - home_logo.width + 2
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)

            away_x = -2
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)

            # Draw Text Elements on Overlay
            # Final Scores (Centered, same position as live)
            home_score = str(game.get("home_score", "0"))
            away_score = str(game.get("away_score", "0"))
            score_text = f"{away_score}-{home_score}"
            score_width = draw_overlay.textlength(score_text, font=self.fonts['score'])
            score_x = (self.display_width - score_width) // 2
            score_y = self.display_height - 14
            self._draw_text_with_outline(draw_overlay, score_text, (score_x, score_y), self.fonts['score'])

            # "Final" text (Top center)
            status_text = game.get("period_text", "Final") # Use formatted period text (e.g., "Final/OT") or default "Final"
            status_width = draw_overlay.textlength(status_text, font=self.fonts['time'])
            status_x = (self.display_width - status_width) // 2
            status_y = 1
            self._draw_text_with_outline(draw_overlay, status_text, (status_x, status_y), self.fonts['time'])

            # Draw odds if available
            if 'odds' in game and game['odds']:
                self._draw_dynamic_odds(draw_overlay, game['odds'], self.display_width, self.display_height)

            # Draw records if enabled
            if self.show_records:
                try:
                    record_font = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
                except IOError:
                    record_font = ImageFont.load_default()
                
                away_record = game.get('away_record', '')
                home_record = game.get('home_record', '')
                
                record_bbox = draw_overlay.textbbox((0,0), "0-0", font=record_font)
                record_height = record_bbox[3] - record_bbox[1]
                record_y = self.display_height - record_height

                if away_record:
                    away_record_x = 0
                    self._draw_text_with_outline(draw_overlay, away_record, (away_record_x, record_y), record_font)

                if home_record:
                    home_record_bbox = draw_overlay.textbbox((0,0), home_record, font=record_font)
                    home_record_width = home_record_bbox[2] - home_record_bbox[0]
                    home_record_x = self.display_width - home_record_width
                    self._draw_text_with_outline(draw_overlay, home_record, (home_record_x, record_y), record_font)

            # Composite and display
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert('RGB')
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display() # Update display here

        except Exception as e:
            self.logger.error(f"[NFL Recent] Error displaying recent game: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display recent games, handling switching."""
        if not self.is_enabled or not self.games_list:
            # If disabled or no games, ensure display might be cleared by main loop if needed
            # Or potentially clear it here? For now, rely on main loop/other managers.
            if not self.games_list and self.current_game:
                 self.current_game = None # Clear internal state if list becomes empty
            return

        try:
            current_time = time.time()

            # Check if it's time to switch games
            if len(self.games_list) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True # Force redraw on switch
                self.logger.debug(f"[NFL Recent] Switched to game index {self.current_game_index}")

            if self.current_game:
                self._draw_scorebug_layout(self.current_game, force_clear)
            # update_display() is called within _draw_scorebug_layout for recent

        except Exception as e:
            self.logger.error(f"[NFL Recent] Error in display loop: {e}", exc_info=True)


class NFLUpcomingManager(BaseNFLManager): # Renamed class
    """Manager for upcoming NFL games."""
    def __init__(self, config: Dict[str, Any], display_manager: DisplayManager, cache_manager: CacheManager):
        super().__init__(config, display_manager, cache_manager)
        self.upcoming_games = [] # Store all fetched upcoming games initially
        self.games_list = [] # Filtered list for display (favorite teams)
        self.current_game_index = 0
        self.last_update = 0
        self.update_interval = 300 # Check for upcoming games every 5 mins
        self.last_log_time = 0
        self.log_interval = 300
        self.last_warning_time = 0
        self.warning_cooldown = 300
        self.last_game_switch = 0
        self.game_display_duration = 15 # Display each upcoming game for 15 seconds
        self.logger.info(f"Initialized NFLUpcomingManager with {len(self.favorite_teams)} favorite teams")

    def update(self):
        """Update upcoming games data."""
        if not self.is_enabled: return
        current_time = time.time()
        if current_time - self.last_update < self.update_interval:
            return

        self.last_update = current_time
        try:
            data = self._fetch_data() # Uses shared cache
            if not data or 'events' not in data:
                self.logger.warning("[NFL Upcoming] No events found in shared data.")
                if not self.games_list: self.current_game = None
                return

            events = data['events']

            # --- Optimization: Filter for favorite teams before extracting details/odds ---
            if self.nfl_config.get("show_favorite_teams_only", False):
                filtered_events = []
                for event in events:
                    try:
                        competitors = event["competitions"][0]["competitors"]
                        if any(c["team"]["abbreviation"] in self.favorite_teams for c in competitors):
                            filtered_events.append(event)
                    except (KeyError, IndexError):
                        continue # Skip event if data structure is unexpected
                events = filtered_events
                self.logger.info(f"[NFL Upcoming] Filtered to {len(events)} events for favorite teams.")

            processed_games = []
            for event in events:
                game = self._extract_game_details(event)
                # Filter criteria: must be upcoming ('pre' state)
                if game and game['is_upcoming']:
                    # This check is now partially redundant if show_favorite_teams_only is true, but harmless
                    # And necessary if show_favorite_teams_only is false but favorite_teams has values
                    if self.nfl_config.get("show_favorite_teams_only", False):
                        if not self.favorite_teams:
                            continue
                        if game['home_abbr'] not in self.favorite_teams and game['away_abbr'] not in self.favorite_teams:
                            continue
                    self._fetch_odds(game)
                    processed_games.append(game)

            # This check is now partially redundant if show_favorite_teams_only is true, but acts as the main filter otherwise
            if self.nfl_config.get("show_favorite_teams_only", False):
                team_games = [game for game in processed_games
                              if game['home_abbr'] in self.favorite_teams or
                                 game['away_abbr'] in self.favorite_teams]
            else:
                team_games = processed_games # Show all upcoming if no favorites

            # Sort by game time, earliest first
            team_games.sort(key=lambda g: g.get('start_time_utc') or datetime.max.replace(tzinfo=self._get_timezone()))
            
            # Limit to the specified number of upcoming games (default 10)
            upcoming_games_to_show = self.nfl_config.get("upcoming_games_to_show", 10)
            self.logger.debug(f"[NFL Upcoming] Limiting to {upcoming_games_to_show} games (found {len(team_games)} total)")
            team_games = team_games[:upcoming_games_to_show]
            self.logger.debug(f"[NFL Upcoming] After limiting: {len(team_games)} games")

            # Log changes or periodically
            should_log = (
                 current_time - self.last_log_time >= self.log_interval or
                 len(team_games) != len(self.games_list) or
                 any(g1['id'] != g2.get('id') for g1, g2 in zip(self.games_list, team_games)) or
                 (not self.games_list and team_games)
             )

            # Check if the list of games to display has changed
            new_game_ids = {g['id'] for g in team_games}
            current_game_ids = {g['id'] for g in self.games_list}

            if new_game_ids != current_game_ids:
                 self.logger.info(f"[NFL Upcoming] Found {len(team_games)} upcoming games within window for display.")
                 self.games_list = team_games
                 if not self.current_game or not self.games_list or self.current_game['id'] not in new_game_ids:
                      self.current_game_index = 0
                      self.current_game = self.games_list[0] if self.games_list else None
                      self.last_game_switch = current_time
                 else:
                      try:
                           self.current_game_index = next(i for i, g in enumerate(self.games_list) if g['id'] == self.current_game['id'])
                           self.current_game = self.games_list[self.current_game_index]
                      except StopIteration:
                           self.current_game_index = 0
                           self.current_game = self.games_list[0]
                           self.last_game_switch = current_time

            elif self.games_list:
                 self.current_game = self.games_list[self.current_game_index] # Update data

            if not self.games_list:
                 self.logger.info("[NFL Upcoming] No relevant upcoming games found to display.")
                 self.current_game = None

            if should_log and not self.games_list:
                 # Log favorite teams only if no games are found and logging is needed
                 self.logger.debug(f"[NFL Upcoming] Favorite teams: {self.favorite_teams}")
                 self.logger.debug(f"[NFL Upcoming] Total upcoming games before filtering: {len(processed_games)}")
                 self.last_log_time = current_time
            elif should_log:
                self.last_log_time = current_time


        except Exception as e:
            self.logger.error(f"[NFL Upcoming] Error updating upcoming games: {e}", exc_info=True)
            # self.current_game = None # Decide if clear on error

    def _draw_scorebug_layout(self, game: Dict, force_clear: bool = False) -> None:
        """Draw the layout for an upcoming NFL game."""
        try:
            main_img = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 255))
            overlay = Image.new('RGBA', (self.display_width, self.display_height), (0, 0, 0, 0))
            draw_overlay = ImageDraw.Draw(overlay)

            home_logo = self._load_and_resize_logo(game["home_abbr"])
            away_logo = self._load_and_resize_logo(game["away_abbr"])

            if not home_logo or not away_logo:
                self.logger.error(f"[NFL Upcoming] Failed to load logos for game: {game.get('id')}")
                draw_final = ImageDraw.Draw(main_img.convert('RGB'))
                self._draw_text_with_outline(draw_final, "Logo Error", (5,5), self.fonts['status'])
                self.display_manager.image.paste(main_img.convert('RGB'), (0, 0))
                self.display_manager.update_display()
                return

            center_y = self.display_height // 2

            # MLB-style logo positions
            home_x = self.display_width - home_logo.width + 2
            home_y = center_y - (home_logo.height // 2)
            main_img.paste(home_logo, (home_x, home_y), home_logo)

            away_x = -2
            away_y = center_y - (away_logo.height // 2)
            main_img.paste(away_logo, (away_x, away_y), away_logo)

            # Draw Text Elements on Overlay
            game_date = game.get("game_date", "")
            game_time = game.get("game_time", "")

            # "Next Game" at the top (use smaller status font)
            status_text = "Next Game"
            status_width = draw_overlay.textlength(status_text, font=self.fonts['status'])
            status_x = (self.display_width - status_width) // 2
            status_y = 1 # Changed from 2
            self._draw_text_with_outline(draw_overlay, status_text, (status_x, status_y), self.fonts['status'])

            # Date text (centered, below "Next Game")
            date_width = draw_overlay.textlength(game_date, font=self.fonts['time'])
            date_x = (self.display_width - date_width) // 2
            # Adjust Y position to stack date and time nicely
            date_y = center_y - 7 # Raise date slightly
            self._draw_text_with_outline(draw_overlay, game_date, (date_x, date_y), self.fonts['time'])

            # Time text (centered, below Date)
            time_width = draw_overlay.textlength(game_time, font=self.fonts['time'])
            time_x = (self.display_width - time_width) // 2
            time_y = date_y + 9 # Place time below date
            self._draw_text_with_outline(draw_overlay, game_time, (time_x, time_y), self.fonts['time'])

            # Draw odds if available
            if 'odds' in game and game['odds']:
                self._draw_dynamic_odds(draw_overlay, game['odds'], self.display_width, self.display_height)

            # Draw records if enabled
            if self.show_records:
                try:
                    record_font = ImageFont.truetype("assets/fonts/4x6-font.ttf", 6)
                except IOError:
                    record_font = ImageFont.load_default()
                
                away_record = game.get('away_record', '')
                home_record = game.get('home_record', '')
                
                record_bbox = draw_overlay.textbbox((0,0), "0-0", font=record_font)
                record_height = record_bbox[3] - record_bbox[1]
                record_y = self.display_height - record_height

                if away_record:
                    away_record_x = 0
                    self._draw_text_with_outline(draw_overlay, away_record, (away_record_x, record_y), record_font)

                if home_record:
                    home_record_bbox = draw_overlay.textbbox((0,0), home_record, font=record_font)
                    home_record_width = home_record_bbox[2] - home_record_bbox[0]
                    home_record_x = self.display_width - home_record_width
                    self._draw_text_with_outline(draw_overlay, home_record, (home_record_x, record_y), record_font)

            # Composite and display
            main_img = Image.alpha_composite(main_img, overlay)
            main_img = main_img.convert('RGB')
            self.display_manager.image.paste(main_img, (0, 0))
            self.display_manager.update_display() # Update display here

        except Exception as e:
            self.logger.error(f"[NFL Upcoming] Error displaying upcoming game: {e}", exc_info=True)

    def display(self, force_clear=False):
        """Display upcoming games, handling switching."""
        if not self.is_enabled: return

        if not self.games_list:
            if self.current_game: self.current_game = None # Clear state if list empty
            current_time = time.time()
            # Log warning periodically if no games found
            if current_time - self.last_warning_time > self.warning_cooldown:
                self.logger.info("[NFL Upcoming] No upcoming games found for favorite teams to display.")
                self.last_warning_time = current_time
            return # Skip display update

        try:
            current_time = time.time()

            # Check if it's time to switch games
            if len(self.games_list) > 1 and current_time - self.last_game_switch >= self.game_display_duration:
                self.current_game_index = (self.current_game_index + 1) % len(self.games_list)
                self.current_game = self.games_list[self.current_game_index]
                self.last_game_switch = current_time
                force_clear = True # Force redraw on switch
                self.logger.debug(f"[NFL Upcoming] Switched to game index {self.current_game_index}")

            if self.current_game:
                self._draw_scorebug_layout(self.current_game, force_clear)
            # update_display() is called within _draw_scorebug_layout for upcoming

        except Exception as e:
            self.logger.error(f"[NFL Upcoming] Error in display loop: {e}", exc_info=True)

