"""
Weather CLI - Beginner & Intermediate Interactive Terminal App
Feature Checklist - Beginner Tier:
- Prompt user to enter a city name or ZIP code
- Make an API call to OpenWeatherMap (or free live global fallback) and parse JSON
- Display: temperature (°C and °F), humidity %, condition description, wind speed
- Handle API errors gracefully: city not found, network timeout, invalid API key
- Input validation: reject empty city input
Developer / Owner: Muhammad Junaid
"""

import sys
import os
from datetime import datetime

from config import DEVELOPER_NAME, APP_NAME, APP_VERSION, load_config, save_config
from weather_service import (
    WeatherService,
    CityNotFoundError,
    InvalidApiKeyError,
    RateLimitError,
    NetworkError,
    ValidationError,
    WeatherAppError
)

# Ensure UTF-8 output on Windows consoles
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Terminal Styling
BLUE = "\033[94m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def print_banner():
    print(f"\n{CYAN}{BOLD}======================================================================{RESET}")
    print(f"{CYAN}{BOLD}   🌤️   {APP_NAME} v{APP_VERSION} - CLI Edition{RESET}")
    print(f"{DIM}        Developed by {BOLD}{DEVELOPER_NAME}{RESET}")
    print(f"{CYAN}{BOLD}======================================================================{RESET}")

def format_weather_display(data: dict):
    city = data.get("city", "Unknown")
    country = data.get("country", "")
    loc_display = f"{city}, {country}" if country else city

    temp_c = data.get("temp_c", 0.0)
    temp_f = data.get("temp_f", 0.0)
    feels_c = data.get("feels_like_c", 0.0)
    feels_f = data.get("feels_like_f", 0.0)
    humidity = data.get("humidity", 0)
    condition = data.get("condition", "N/A")
    description = data.get("description", condition)
    wind_ms = data.get("wind_speed_ms", 0.0)
    wind_mph = data.get("wind_speed_mph", 0.0)
    wind_kmh = data.get("wind_speed_kmh", 0.0)
    wind_dir = data.get("wind_dir", "")
    pressure = data.get("pressure", 0)
    visibility_km = data.get("visibility_km", 0.0)
    sunrise = data.get("sunrise", "N/A")
    sunset = data.get("sunset", "N/A")
    source = data.get("source", "Weather API")
    updated = data.get("updated_time", "")

    print(f"\n{GREEN}{BOLD}📍 Location:       {WHITE_TEXT(loc_display)} (Lat {round(data.get('lat', 0), 2)}, Lon {round(data.get('lon', 0), 2)}){RESET}")
    print(f"{YELLOW}🕒 Local Report:   {updated}  |  Source: {source}{RESET}")
    print(f"{CYAN}----------------------------------------------------------------------{RESET}")
    print(f"  🌡️  {BOLD}Temperature:{RESET}    {BOLD}{temp_c}°C{RESET}  /  {BOLD}{temp_f}°F{RESET}  (Feels like {feels_c}°C / {feels_f}°F)")
    print(f"  ☁️  {BOLD}Condition:{RESET}      {BOLD}{description}{RESET} ({condition})")
    print(f"  💧  {BOLD}Humidity:{RESET}       {BOLD}{humidity}%{RESET}")
    print(f"  💨  {BOLD}Wind Speed:{RESET}     {BOLD}{wind_ms} m/s{RESET} ({wind_kmh} km/h  |  {wind_mph} mph) from {BOLD}{wind_dir}{RESET}")
    print(f"  🧭  {BOLD}Pressure:{RESET}       {pressure} hPa")
    print(f"  👁️  {BOLD}Visibility:{RESET}     {visibility_km} km")
    print(f"  🌅  {BOLD}Sunrise / Set:{RESET}  {sunrise}  /  {sunset}")
    print(f"{CYAN}----------------------------------------------------------------------{RESET}")

    # Hourly Forecast
    hourly = data.get("hourly", [])
    if hourly:
        print(f"\n{BOLD}⏱️  Hourly Forecast (Next 6-12 Hours):{RESET}")
        header = f"   {'Time':<8} {'Condition':<18} {'Temp (°C)':<12} {'Temp (°F)':<12} {'Rain Prob':<10}"
        print(f"{DIM}{header}{RESET}")
        print(f"   {'-'*60}")
        for item in hourly[:6]:
            t = item.get("time", "")
            cond = item.get("condition", "")[:16]
            tc = f"{item.get('temp_c')}°C"
            tf = f"{item.get('temp_f')}°F"
            pop = f"{item.get('pop')}%"
            print(f"   {t:<8} {cond:<18} {tc:<12} {tf:<12} {pop:<10}")

    # Daily Forecast
    daily = data.get("daily", [])
    if daily:
        print(f"\n{BOLD}📅  5-Day Forecast:{RESET}")
        d_header = f"   {'Day':<6} {'Date':<10} {'Condition':<18} {'Min Temp':<14} {'Max Temp':<14}"
        print(f"{DIM}{d_header}{RESET}")
        print(f"   {'-'*60}")
        for d in daily[:5]:
            day = d.get("day", "")
            dt = d.get("date", "")
            cond = d.get("condition", "")[:16]
            min_t = f"{d.get('min_c')}°C / {d.get('min_f')}°F"
            max_t = f"{d.get('max_c')}°C / {d.get('max_f')}°F"
            print(f"   {day:<6} {dt:<10} {cond:<18} {min_t:<14} {max_t:<14}")
    print()

def WHITE_TEXT(text: str) -> str:
    return f"{BOLD}{text}{RESET}"

def run_cli():
    """Interactive loop for CLI weather app."""
    # Enable Windows ANSI colors if supported
    os.system("")
    config = load_config()
    weather_service = WeatherService(api_key=config.get("owm_api_key", ""))

    print_banner()

    if weather_service.has_api_key():
        print(f"{GREEN}✓ OpenWeatherMap API Key active.{RESET}")
    else:
        print(f"{YELLOW}ℹ Running in Free Live Global API mode.{RESET}")
        print(f"{DIM}  Tip: You can set an OpenWeatherMap API key by typing 'key' at the prompt.{RESET}")

    while True:
        try:
            prompt_text = (
                f"\n{BOLD}Enter city name, ZIP code, 'auto' (detect location), 'key' (config), or 'exit':{RESET} "
            )
            user_input = input(prompt_text).strip()

            # Input validation: reject empty input
            if not user_input:
                print(f"{RED}⚠️ Input cannot be empty. Please enter a city name or ZIP code.{RESET}")
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                print(f"\n{CYAN}Thank you for using {APP_NAME}. Have a great day! — Muhammad Junaid{RESET}\n")
                break

            if user_input.lower() == "key":
                current_key = config.get("owm_api_key", "")
                mask = f"{current_key[:4]}...{current_key[-4:]}" if len(current_key) > 8 else (current_key or "None")
                print(f"\nCurrent OpenWeatherMap API Key: {BOLD}{mask}{RESET}")
                new_key = input("Enter new OpenWeatherMap API key (press Enter to keep current, 'clear' to remove): ").strip()
                if new_key.lower() == "clear":
                    config["owm_api_key"] = ""
                    save_config(config)
                    weather_service.set_api_key("")
                    print(f"{YELLOW}OpenWeatherMap key removed. Using Free Live Global API.{RESET}")
                elif new_key:
                    config["owm_api_key"] = new_key
                    save_config(config)
                    weather_service.set_api_key(new_key)
                    print(f"{GREEN}✓ API Key updated and saved.{RESET}")
                continue

            if user_input.lower() in ("auto", "locate", "my location"):
                print(f"{CYAN}📡 Detecting your location via ipinfo.io...{RESET}")
                loc_res = weather_service.detect_user_location()
                if loc_res.get("success"):
                    city = loc_res.get("city", "London")
                    country = loc_res.get("country", "")
                    print(f"{GREEN}✓ Location detected: {city}, {country}{RESET}")
                    user_input = city
                else:
                    print(f"{RED}Could not detect location automatically. Falling back to London.{RESET}")
                    user_input = "London"

            print(f"{CYAN}⏳ Fetching real-time weather data for '{user_input}'...{RESET}")
            try:
                data = weather_service.fetch_weather(user_input)
                format_weather_display(data)
                # Remember last city
                config["last_city"] = user_input
                save_config(config)

            except CityNotFoundError as e:
                print(f"{RED}❌ Error: {str(e)}{RESET}")
                print(f"{YELLOW}💡 Tip: Check for typos, or include the country code (e.g. 'Paris, FR' or '90210, US').{RESET}")
            except InvalidApiKeyError as e:
                print(f"{RED}❌ API Key Error: {str(e)}{RESET}")
                print(f"{YELLOW}💡 Tip: Type 'key' to update your OpenWeatherMap API key or 'clear' to use the Free Global mode.{RESET}")
            except RateLimitError as e:
                print(f"{YELLOW}⚠️ Rate Limit: {str(e)}{RESET}")
            except NetworkError as e:
                print(f"{RED}🌐 Network Error: {str(e)}{RESET}")
            except WeatherAppError as e:
                print(f"{RED}⚠️ Weather Error: {str(e)}{RESET}")
            except Exception as e:
                print(f"{RED}⚠️ Unexpected error occurred: {str(e)}{RESET}")

        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{CYAN}Session ended. Developed by {DEVELOPER_NAME}.{RESET}\n")
            break

if __name__ == "__main__":
    run_cli()
