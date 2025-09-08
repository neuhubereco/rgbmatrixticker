import requests
import json
import os
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Define paths relative to this file's location (assuming it's in src)
CONFIG_DIR = os.path.join(os.path.dirname(__file__), '..', 'config')
CONFIG_PATH = os.path.join(CONFIG_DIR, 'config.json')
YTM_AUTH_CONFIG_PATH = os.path.join(CONFIG_DIR, 'ytm_auth.json')

# Resolve to absolute paths
CONFIG_DIR = os.path.abspath(CONFIG_DIR)
CONFIG_PATH = os.path.abspath(CONFIG_PATH)
YTM_AUTH_CONFIG_PATH = os.path.abspath(YTM_AUTH_CONFIG_PATH)

# YTM Companion App Constants (copied from ytm_client.py)
YTM_APP_ID = "ledmatrixcontroller"
YTM_APP_NAME = "LEDMatrixController"
YTM_APP_VERSION = "1.0.0"

def load_ytm_companion_url():
    """Loads YTM_COMPANION_URL from config.json"""
    default_url = "http://localhost:9863"
    base_url = default_url

    if not os.path.exists(CONFIG_PATH):
        logging.warning(f"Main config file not found at {CONFIG_PATH}. Using default YTM URL: {base_url}")
        return base_url

    try:
        with open(CONFIG_PATH, 'r') as f:
            loaded_config = json.load(f)
            music_config = loaded_config.get("music", {})
            base_url = music_config.get("YTM_COMPANION_URL", default_url)
            if not base_url:
                logging.warning("YTM_COMPANION_URL missing or empty in config.json music section. Using default.")
                base_url = default_url
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from main config {CONFIG_PATH}. Using default YTM URL.")
        base_url = default_url
    except Exception as e:
        logging.error(f"Error loading YTM_COMPANION_URL from main config {CONFIG_PATH}: {e}. Using default YTM URL.")
        base_url = default_url
    
    logging.info(f"YTM Companion URL set to: {base_url}")
    
    if base_url.startswith("ws://"):
        base_url = "http://" + base_url[5:]
    elif base_url.startswith("wss://"):
        base_url = "https://" + base_url[6:]
    return base_url

def _request_auth_code(base_url):
    """Requests an authentication code from the YTM Companion server."""
    url = f"{base_url}/api/v1/auth/requestcode"
    payload = {
        "appId": YTM_APP_ID,
        "appName": YTM_APP_NAME,
        "appVersion": YTM_APP_VERSION
    }
    try:
        logging.info(f"Requesting auth code from {url} with appId: {YTM_APP_ID}")
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        auth_code = data.get('code')
        if auth_code:
            logging.info(f"Received auth code: {auth_code}")
        else:
            logging.error("Auth code not found in response.")
        return auth_code
    except requests.exceptions.RequestException as e:
        logging.error(f"Error requesting YTM auth code: {e}")
        return None
    except json.JSONDecodeError:
        logging.error("Error decoding JSON response when requesting auth code.")
        return None

def _request_auth_token(base_url, code):
    """Requests an authentication token using the provided code."""
    if not code:
        return None
    url = f"{base_url}/api/v1/auth/request"
    payload = {
        "appId": YTM_APP_ID,
        "code": code
    }
    try:
        logging.info("Requesting auth token. PLEASE CHECK YOUR YTM DESKTOP APP TO APPROVE THIS REQUEST.")
        logging.info("You have 30 seconds to approve in the YTM Desktop App.")
        response = requests.post(url, json=payload, timeout=35)
        response.raise_for_status()
        data = response.json()
        token = data.get('token')
        if token:
            logging.info("Successfully received YTM auth token.")
        else:
            logging.warning("Auth token not found in response.")
        return token
    except requests.exceptions.Timeout:
        logging.error("Timeout waiting for YTM auth token. Did you approve the request in YTM Desktop App?")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error requesting YTM auth token: {e}")
        return None
    except json.JSONDecodeError:
        logging.error("Error decoding JSON response when requesting auth token.")
        return None

def save_ytm_token(token):
    """Saves the YTM token to ytm_auth.json."""
    if not token:
        logging.warning("No YTM token provided to save.")
        return False

    if not os.path.exists(CONFIG_DIR):
        try:
            os.makedirs(CONFIG_DIR)
            logging.info(f"Created config directory: {CONFIG_DIR}")
        except OSError as e:
            logging.error(f"Could not create config directory {CONFIG_DIR}: {e}")
            return False

    token_data = {"YTM_COMPANION_TOKEN": token}

    try:
        with open(YTM_AUTH_CONFIG_PATH, 'w') as f:
            json.dump(token_data, f, indent=4)
        logging.info(f"YTM Companion token saved to {YTM_AUTH_CONFIG_PATH}")
        return True
    except Exception as e:
        logging.error(f"Error saving YTM token to {YTM_AUTH_CONFIG_PATH}: {e}")
        return False

if __name__ == "__main__":
    logging.info("Starting YTM Authentication Process...")
    
    # Ensure the config directory exists, create if not
    # This is important because this script is run as the user.
    if not os.path.exists(CONFIG_DIR):
        try:
            logging.info(f"Config directory {CONFIG_DIR} not found. Attempting to create it.")
            os.makedirs(CONFIG_DIR)
            logging.info(f"Successfully created config directory: {CONFIG_DIR}")
        except OSError as e:
            logging.error(f"Fatal: Could not create config directory {CONFIG_DIR}: {e}")
            logging.error("Please ensure the path is correct and you have permissions to create this directory.")
            exit(1) # Exit if we can't create the config directory

    ytm_url = load_ytm_companion_url()
    if not ytm_url:
        logging.error("Could not determine YTM Companion URL. Exiting.")
        exit(1)

    auth_code = _request_auth_code(ytm_url)
    if not auth_code:
        logging.error("Failed to get YTM auth code. Cannot proceed with authentication. Exiting.")
        exit(1)
    
    auth_token = _request_auth_token(ytm_url, auth_code)
    if auth_token:
        if save_ytm_token(auth_token):
            logging.info("YTM authentication successful and token saved.")
        else:
            logging.error("YTM authentication successful, but FAILED to save token.")
            logging.error(f"Please check permissions for the directory {CONFIG_DIR} and the file {YTM_AUTH_CONFIG_PATH} if it exists.")
    else:
        logging.error("Failed to get YTM auth token. Authentication unsuccessful.")

    logging.info("YTM Authentication Process Finished.") 