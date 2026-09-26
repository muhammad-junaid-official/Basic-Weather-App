"""
Configuration and constants for Basic Weather App
Developer / Owner: Muhammad Junaid
"""

import os
import json
from pathlib import Path

# Developer Attribution
DEVELOPER_NAME = "Muhammad Junaid"
APP_NAME = "SkyPulse Weather App"
APP_VERSION = "2.0.0"
REPO_URL = "https://github.com/muhammad-junaid-official/Basic-Weather-App.git"

# Paths
BASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = BASE_DIR / "config.json"
CACHE_DIR = BASE_DIR / "assets" / "cache"
ICONS_DIR = BASE_DIR / "assets" / "icons"

# Ensure directories exist
CACHE_DIR.mkdir(parents=True, exist_ok=True)
ICONS_DIR.mkdir(parents=True, exist_ok=True)

# Default Settings
DEFAULT_CONFIG = {
    "owm_api_key": "",          # User can provide an OpenWeatherMap API key
    "unit": "metric",           # 'metric' (°C) or 'imperial' (°F)
    "last_city": "London",
    "auto_detect_location": True,
    "theme": "dark"
}

def load_config() -> dict:
    """Load configuration from config.json or environment variable."""
    config = DEFAULT_CONFIG.copy()
    
    # Check environment variable first
    env_key = os.environ.get("OPENWEATHERMAP_API_KEY")
    if env_key:
        config["owm_api_key"] = env_key

    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception:
            pass

    return config

def save_config(config_data: dict) -> bool:
    """Save configuration to config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4)
        return True
    except Exception:
        return False
