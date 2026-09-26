"""
Weather Service Module for Basic Weather App
Handles API calls, JSON parsing, error handling, location detection, and icon caching.
Developer / Owner: Muhammad Junaid
"""

import io
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import requests
from PIL import Image, ImageDraw, ImageFont

from config import CACHE_DIR, ICONS_DIR, DEVELOPER_NAME

# Custom Exception Hierarchy for Clear Error Handling
class WeatherAppError(Exception):
    """Base exception for weather app."""
    pass

class CityNotFoundError(WeatherAppError):
    """Raised when the requested city or zip code is not found."""
    pass

class InvalidApiKeyError(WeatherAppError):
    """Raised when the OpenWeatherMap API key is invalid or unauthorized."""
    pass

class RateLimitError(WeatherAppError):
    """Raised when the API rate limit is exceeded."""
    pass

class NetworkError(WeatherAppError):
    """Raised when a network timeout or connection failure occurs."""
    pass

class ValidationError(WeatherAppError):
    """Raised when user input fails validation."""
    pass


class WeatherService:
    """Service to fetch, parse, and process weather data."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key.strip()
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": f"SkyPulseWeatherApp/{DEVELOPER_NAME}"
        })

    def set_api_key(self, api_key: str):
        self.api_key = api_key.strip()

    def has_api_key(self) -> bool:
        return bool(self.api_key)

    @staticmethod
    def detect_user_location(timeout: int = 6) -> Dict[str, Any]:
        """
        Detect user location automatically using IP address via ipinfo.io API (free tier).
        Returns a dict with city, country, region, lat, lon.
        """
        try:
            resp = requests.get("https://ipinfo.io/json", timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                loc = data.get("loc", "").split(",")
                lat = float(loc[0]) if len(loc) == 2 else 0.0
                lon = float(loc[1]) if len(loc) == 2 else 0.0
                return {
                    "success": True,
                    "city": data.get("city", "London"),
                    "region": data.get("region", ""),
                    "country": data.get("country", ""),
                    "lat": lat,
                    "lon": lon,
                    "ip": data.get("ip", "")
                }
        except Exception as e:
            return {"success": False, "error": str(e), "city": "London", "country": "GB"}
        return {"success": False, "error": "Unable to detect location", "city": "London", "country": "GB"}

    def fetch_weather(self, query: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Main entry to fetch weather data for a city or ZIP code.
        If OpenWeatherMap API key is available, calls OpenWeatherMap.
        Otherwise falls back cleanly to the Open-Meteo free global API so the app works instantly.
        """
        query = query.strip()
        if not query:
            raise ValidationError("Please enter a valid city name or ZIP code.")

        if self.has_api_key():
            try:
                return self._fetch_openweathermap(query, timeout=timeout)
            except InvalidApiKeyError:
                # If key was explicitly invalid, re-raise so user knows to fix key
                raise
            except (CityNotFoundError, RateLimitError):
                raise
            except Exception as e:
                # If network error or unexpected issue, attempt fallback with warning
                raise NetworkError(f"Connection to OpenWeatherMap failed: {str(e)}")
        else:
            # Fallback to Free Open-Meteo global live weather engine
            return self._fetch_openmeteo(query, timeout=timeout)

    def fetch_weather_by_coords(self, lat: float, lon: float, location_name: str = "", timeout: int = 10) -> Dict[str, Any]:
        """Fetch weather data using geographic coordinates."""
        if self.has_api_key():
            return self._fetch_openweathermap_coords(lat, lon, timeout=timeout)
        else:
            return self._fetch_openmeteo_coords(lat, lon, location_name=location_name, timeout=timeout)

    # -------------------------------------------------------------------------
    # OpenWeatherMap Integration
    # -------------------------------------------------------------------------
    def _fetch_openweathermap(self, query: str, timeout: int = 10) -> Dict[str, Any]:
        """Fetch current weather and 5-day forecast from OpenWeatherMap."""
        # Detect if query looks like a US or international zip code (all digits or digits+comma)
        is_zip = query.replace(" ", "").replace(",", "").isdigit()
        
        base_current = "https://api.openweathermap.org/data/2.5/weather"
        base_forecast = "https://api.openweathermap.org/data/2.5/forecast"
        
        params_curr = {"appid": self.api_key, "units": "metric"}
        params_fore = {"appid": self.api_key, "units": "metric"}

        if is_zip:
            params_curr["zip"] = query
            params_fore["zip"] = query
        else:
            params_curr["q"] = query
            params_fore["q"] = query

        try:
            resp_curr = self.session.get(base_current, params=params_curr, timeout=timeout)
            self._handle_owm_status_code(resp_curr, query)
            curr_data = resp_curr.json()
        except requests.exceptions.Timeout:
            raise NetworkError("Connection timed out while reaching OpenWeatherMap. Please try again.")
        except requests.exceptions.ConnectionError:
            raise NetworkError("Network error. Please check your internet connection.")

        # Fetch 5-day / 3-hour forecast
        forecast_data = {}
        try:
            resp_fore = self.session.get(base_forecast, params=params_fore, timeout=timeout)
            if resp_fore.status_code == 200:
                forecast_data = resp_fore.json()
        except Exception:
            forecast_data = {}

        return self._parse_owm_response(curr_data, forecast_data)

    def _fetch_openweathermap_coords(self, lat: float, lon: float, timeout: int = 10) -> Dict[str, Any]:
        """Fetch OpenWeatherMap by coordinates."""
        base_current = "https://api.openweathermap.org/data/2.5/weather"
        base_forecast = "https://api.openweathermap.org/data/2.5/forecast"
        
        params = {"lat": lat, "lon": lon, "appid": self.api_key, "units": "metric"}
        try:
            resp_curr = self.session.get(base_current, params=params, timeout=timeout)
            self._handle_owm_status_code(resp_curr, f"lat={lat}, lon={lon}")
            curr_data = resp_curr.json()
            
            resp_fore = self.session.get(base_forecast, params=params, timeout=timeout)
            forecast_data = resp_fore.json() if resp_fore.status_code == 200 else {}
            return self._parse_owm_response(curr_data, forecast_data)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            raise NetworkError(f"Network error: {str(e)}")

    def _handle_owm_status_code(self, resp: requests.Response, query: str):
        if resp.status_code == 200:
            return
        elif resp.status_code == 401:
            raise InvalidApiKeyError(
                "Invalid OpenWeatherMap API key. Please check your API key in Settings or environment variables."
            )
        elif resp.status_code == 404:
            raise CityNotFoundError(
                f"Location '{query}' not found. Please verify the city spelling or ZIP code."
            )
        elif resp.status_code == 429:
            raise RateLimitError("OpenWeatherMap API call limit reached (60 calls/minute). Please wait a moment.")
        else:
            try:
                err_msg = resp.json().get("message", resp.text)
            except Exception:
                err_msg = resp.text
            raise WeatherAppError(f"OpenWeatherMap Error ({resp.status_code}): {err_msg}")

    def _parse_owm_response(self, curr: Dict[str, Any], forecast: Dict[str, Any]) -> Dict[str, Any]:
        """Parse raw OpenWeatherMap response into unified structure."""
        main = curr.get("main", {})
        weather_list = curr.get("weather", [{}])
        weather_primary = weather_list[0] if weather_list else {}
        wind = curr.get("wind", {})
        sys = curr.get("sys", {})

        temp_c = float(main.get("temp", 0.0))
        feels_like_c = float(main.get("feels_like", temp_c))
        temp_min_c = float(main.get("temp_min", temp_c))
        temp_max_c = float(main.get("temp_max", temp_c))
        humidity = int(main.get("humidity", 0))
        pressure = int(main.get("pressure", 1013))
        wind_speed_ms = float(wind.get("speed", 0.0))
        wind_deg = int(wind.get("deg", 0))
        visibility_m = curr.get("visibility", 10000)
        visibility_km = round(visibility_m / 1000, 1)

        sunrise_ts = sys.get("sunrise", 0)
        sunset_ts = sys.get("sunset", 0)
        sunrise_str = datetime.fromtimestamp(sunrise_ts).strftime("%I:%M %p") if sunrise_ts else "N/A"
        sunset_str = datetime.fromtimestamp(sunset_ts).strftime("%I:%M %p") if sunset_ts else "N/A"

        condition = weather_primary.get("main", "Clear")
        description = weather_primary.get("description", condition).title()
        icon_code = weather_primary.get("icon", "01d")

        # Parse Hourly Forecast (next 6-8 steps, 3h each = next 18-24 hours)
        hourly_list = []
        raw_forecast_list = forecast.get("list", [])
        for item in raw_forecast_list[:8]:
            dt = datetime.fromtimestamp(item.get("dt", 0))
            item_main = item.get("main", {})
            item_weather = (item.get("weather") or [{}])[0]
            item_temp_c = float(item_main.get("temp", 0.0))
            pop = int(float(item.get("pop", 0.0)) * 100)
            hourly_list.append({
                "time": dt.strftime("%I %p").lstrip("0"),
                "full_time": dt.strftime("%I:%M %p"),
                "temp_c": round(item_temp_c, 1),
                "temp_f": round(c_to_f(item_temp_c), 1),
                "condition": item_weather.get("main", "Clear"),
                "description": item_weather.get("description", "").title(),
                "icon_code": item_weather.get("icon", "01d"),
                "pop": pop
            })

        # Parse Daily Forecast (group next 5 days)
        daily_dict = {}
        for item in raw_forecast_list:
            dt = datetime.fromtimestamp(item.get("dt", 0))
            day_key = dt.strftime("%Y-%m-%d")
            # Skip today's remainder if we want future days
            item_main = item.get("main", {})
            item_weather = (item.get("weather") or [{}])[0]
            item_temp_min = float(item_main.get("temp_min", 0.0))
            item_temp_max = float(item_main.get("temp_max", 0.0))
            
            if day_key not in daily_dict:
                daily_dict[day_key] = {
                    "day": dt.strftime("%a"),
                    "date": dt.strftime("%b %d"),
                    "min_c": item_temp_min,
                    "max_c": item_temp_max,
                    "condition": item_weather.get("main", "Clear"),
                    "description": item_weather.get("description", "").title(),
                    "icon_code": item_weather.get("icon", "01d")
                }
            else:
                daily_dict[day_key]["min_c"] = min(daily_dict[day_key]["min_c"], item_temp_min)
                daily_dict[day_key]["max_c"] = max(daily_dict[day_key]["max_c"], item_temp_max)

        daily_list = []
        for _, day_data in list(daily_dict.items())[:5]:
            min_c = round(day_data["min_c"], 1)
            max_c = round(day_data["max_c"], 1)
            daily_list.append({
                "day": day_data["day"],
                "date": day_data["date"],
                "min_c": min_c,
                "min_f": round(c_to_f(min_c), 1),
                "max_c": max_c,
                "max_f": round(c_to_f(max_c), 1),
                "condition": day_data["condition"],
                "description": day_data["description"],
                "icon_code": day_data["icon_code"]
            })

        return {
            "city": curr.get("name", "Unknown Location"),
            "country": sys.get("country", ""),
            "lat": curr.get("coord", {}).get("lat", 0.0),
            "lon": curr.get("coord", {}).get("lon", 0.0),
            "temp_c": round(temp_c, 1),
            "temp_f": round(c_to_f(temp_c), 1),
            "feels_like_c": round(feels_like_c, 1),
            "feels_like_f": round(c_to_f(feels_like_c), 1),
            "temp_min_c": round(temp_min_c, 1),
            "temp_min_f": round(c_to_f(temp_min_c), 1),
            "temp_max_c": round(temp_max_c, 1),
            "temp_max_f": round(c_to_f(temp_max_c), 1),
            "humidity": humidity,
            "pressure": pressure,
            "wind_speed_ms": round(wind_speed_ms, 1),
            "wind_speed_mph": round(wind_speed_ms * 2.23694, 1),
            "wind_speed_kmh": round(wind_speed_ms * 3.6, 1),
            "wind_deg": wind_deg,
            "wind_dir": deg_to_compass(wind_deg),
            "visibility_km": visibility_km,
            "visibility_mi": round(visibility_km * 0.621371, 1),
            "sunrise": sunrise_str,
            "sunset": sunset_str,
            "condition": condition,
            "description": description,
            "icon_code": icon_code,
            "updated_time": datetime.now().strftime("%I:%M %p"),
            "source": "OpenWeatherMap API",
            "hourly": hourly_list,
            "daily": daily_list
        }

    # -------------------------------------------------------------------------
    # Open-Meteo Integration (Instant Live Global Weather Fallback)
    # -------------------------------------------------------------------------
    def _fetch_openmeteo(self, query: str, timeout: int = 10) -> Dict[str, Any]:
        """Geocodes city name and fetches real-time forecast from Open-Meteo."""
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={requests.utils.quote(query)}&count=1"
        try:
            geo_resp = self.session.get(geo_url, timeout=timeout)
            if geo_resp.status_code != 200:
                raise CityNotFoundError(f"City '{query}' not found.")
            geo_data = geo_resp.json()
            results = geo_data.get("results")
            if not results:
                raise CityNotFoundError(f"Location '{query}' not found. Please check spelling.")
            
            first = results[0]
            lat = first.get("latitude")
            lon = first.get("longitude")
            city_name = first.get("name", query)
            country = first.get("country_code", first.get("country", ""))
            return self._fetch_openmeteo_coords(lat, lon, location_name=city_name, country=country, timeout=timeout)
        except requests.exceptions.Timeout:
            raise NetworkError("Connection timed out. Please check your internet connection.")
        except requests.exceptions.ConnectionError:
            raise NetworkError("Unable to connect. Please check your internet connection.")

    def _fetch_openmeteo_coords(self, lat: float, lon: float, location_name: str = "", country: str = "", timeout: int = 10) -> Dict[str, Any]:
        """Fetches Open-Meteo forecast by coordinates and builds unified model."""
        url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
            "&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,weather_code"
            "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset&timezone=auto"
        )
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code != 200:
                raise WeatherAppError(f"Weather API error ({resp.status_code})")
            data = resp.json()
        except requests.exceptions.Timeout:
            raise NetworkError("Connection timed out.")
        except requests.exceptions.ConnectionError:
            raise NetworkError("Network connection error.")

        curr = data.get("current", {})
        temp_c = float(curr.get("temperature_2m", 0.0))
        feels_c = float(curr.get("apparent_temperature", temp_c))
        humidity = int(curr.get("relative_humidity_2m", 0))
        wcode = int(curr.get("weather_code", 0))
        is_day = bool(curr.get("is_day", 1))
        wind_kmh = float(curr.get("wind_speed_10m", 0.0))
        wind_ms = round(wind_kmh / 3.6, 1)
        wind_deg = int(curr.get("wind_direction_10m", 0))
        pressure = int(curr.get("surface_pressure", 1013))

        cond_title, cond_desc, icon_code = map_wmo_code(wcode, is_day)

        # Daily details
        daily_raw = data.get("daily", {})
        daily_times = daily_raw.get("time", [])
        daily_max = daily_raw.get("temperature_2m_max", [])
        daily_min = daily_raw.get("temperature_2m_min", [])
        daily_codes = daily_raw.get("weather_code", [])
        sunrises = daily_raw.get("sunrise", [])
        sunsets = daily_raw.get("sunset", [])

        sunrise_str = "N/A"
        sunset_str = "N/A"
        if sunrises:
            try:
                sunrise_str = datetime.fromisoformat(sunrises[0]).strftime("%I:%M %p")
            except Exception:
                sunrise_str = str(sunrises[0])
        if sunsets:
            try:
                sunset_str = datetime.fromisoformat(sunsets[0]).strftime("%I:%M %p")
            except Exception:
                sunset_str = str(sunsets[0])

        daily_list = []
        for i in range(min(5, len(daily_times))):
            try:
                dt_obj = datetime.fromisoformat(daily_times[i])
                day_name = dt_obj.strftime("%a")
                date_str = dt_obj.strftime("%b %d")
            except Exception:
                day_name = f"Day {i+1}"
                date_str = ""
            
            d_max = round(float(daily_max[i]), 1) if i < len(daily_max) else temp_c
            d_min = round(float(daily_min[i]), 1) if i < len(daily_min) else temp_c
            d_code = int(daily_codes[i]) if i < len(daily_codes) else 0
            d_cond, d_desc, d_icon = map_wmo_code(d_code, True)
            daily_list.append({
                "day": day_name,
                "date": date_str,
                "min_c": d_min,
                "min_f": round(c_to_f(d_min), 1),
                "max_c": d_max,
                "max_f": round(c_to_f(d_max), 1),
                "condition": d_cond,
                "description": d_desc,
                "icon_code": d_icon
            })

        # Hourly forecast: next 8 hours
        hourly_raw = data.get("hourly", {})
        h_times = hourly_raw.get("time", [])
        h_temps = hourly_raw.get("temperature_2m", [])
        h_codes = hourly_raw.get("weather_code", [])
        h_pops = hourly_raw.get("precipitation_probability", [])
        
        # Find current hour index
        current_hour_idx = 0
        now_iso_prefix = datetime.now().strftime("%Y-%m-%dT%H")
        for idx, t_str in enumerate(h_times):
            if t_str.startswith(now_iso_prefix):
                current_hour_idx = idx
                break

        hourly_list = []
        for i in range(current_hour_idx, min(current_hour_idx + 8, len(h_times))):
            try:
                h_dt = datetime.fromisoformat(h_times[i])
                h_time_str = h_dt.strftime("%I %p").lstrip("0")
                h_full = h_dt.strftime("%I:%M %p")
            except Exception:
                h_time_str = f"+{i-current_hour_idx}h"
                h_full = h_time_str

            h_c = round(float(h_temps[i]), 1) if i < len(h_temps) else temp_c
            h_code = int(h_codes[i]) if i < len(h_codes) else 0
            h_cond, h_desc, h_icon = map_wmo_code(h_code, True)
            h_pop = int(h_pops[i]) if i < len(h_pops) and h_pops[i] is not None else 0

            hourly_list.append({
                "time": h_time_str,
                "full_time": h_full,
                "temp_c": h_c,
                "temp_f": round(c_to_f(h_c), 1),
                "condition": h_cond,
                "description": h_desc,
                "icon_code": h_icon,
                "pop": h_pop
            })

        t_min_c = daily_list[0]["min_c"] if daily_list else temp_c
        t_max_c = daily_list[0]["max_c"] if daily_list else temp_c

        return {
            "city": location_name or f"Lat {round(lat, 2)}, Lon {round(lon, 2)}",
            "country": country,
            "lat": lat,
            "lon": lon,
            "temp_c": round(temp_c, 1),
            "temp_f": round(c_to_f(temp_c), 1),
            "feels_like_c": round(feels_c, 1),
            "feels_like_f": round(c_to_f(feels_c), 1),
            "temp_min_c": round(t_min_c, 1),
            "temp_min_f": round(c_to_f(t_min_c), 1),
            "temp_max_c": round(t_max_c, 1),
            "temp_max_f": round(c_to_f(t_max_c), 1),
            "humidity": humidity,
            "pressure": pressure,
            "wind_speed_ms": wind_ms,
            "wind_speed_mph": round(wind_ms * 2.23694, 1),
            "wind_speed_kmh": round(wind_kmh, 1),
            "wind_deg": wind_deg,
            "wind_dir": deg_to_compass(wind_deg),
            "visibility_km": 10.0,
            "visibility_mi": 6.2,
            "sunrise": sunrise_str,
            "sunset": sunset_str,
            "condition": cond_title,
            "description": cond_desc,
            "icon_code": icon_code,
            "updated_time": datetime.now().strftime("%I:%M %p"),
            "source": "Open-Meteo Free API (Live Global)",
            "hourly": hourly_list,
            "daily": daily_list
        }

    # -------------------------------------------------------------------------
    # Icon Caching and Rendering
    # -------------------------------------------------------------------------
    def get_weather_icon(self, icon_code: str, size: Tuple[int, int] = (64, 64)) -> Optional[Image.Image]:
        """
        Retrieves weather icon from local cache or downloads from OpenWeatherMap CDN.
        Falls back to generating a beautiful vector PIL image if offline.
        """
        icon_path = CACHE_DIR / f"{icon_code}.png"
        
        # Check cache
        if icon_path.exists():
            try:
                img = Image.open(icon_path).convert("RGBA")
                return img.resize(size, Image.Resampling.LANCZOS)
            except Exception:
                pass

        # Attempt download from OpenWeatherMap icon CDN (Publicly accessible)
        icon_url = f"https://openweathermap.org/img/wn/{icon_code}@2x.png"
        try:
            resp = self.session.get(icon_url, timeout=4)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content)).convert("RGBA")
                img.save(icon_path, format="PNG")
                return img.resize(size, Image.Resampling.LANCZOS)
        except Exception:
            pass

        # Fallback to programmatic high-contrast PIL weather graphic
        return self._generate_fallback_icon(icon_code, size)

    def _generate_fallback_icon(self, icon_code: str, size: Tuple[int, int]) -> Image.Image:
        """Dynamically generate a stylized weather icon when network is unavailable."""
        w, h = size
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Color schemes based on condition code
        if icon_code.startswith("01"):  # Sun / Clear
            # Warm Glowing Sun
            pad = int(w * 0.15)
            draw.ellipse([pad, pad, w - pad, h - pad], fill="#F59E0B", outline="#FBBF24", width=2)
        elif icon_code.startswith("02") or icon_code.startswith("03") or icon_code.startswith("04"):  # Clouds
            # Stylized Cloud
            draw.ellipse([int(w*0.2), int(h*0.35), int(w*0.6), int(h*0.75)], fill="#94A3B8")
            draw.ellipse([int(w*0.45), int(h*0.25), int(w*0.8), int(h*0.7)], fill="#CBD5E1")
            draw.rounded_rectangle([int(w*0.2), int(h*0.5), int(w*0.8), int(h*0.8)], radius=8, fill="#94A3B8")
        elif icon_code.startswith("09") or icon_code.startswith("10"):  # Rain
            # Cloud + Raindrops
            draw.ellipse([int(w*0.2), int(h*0.25), int(w*0.8), int(h*0.65)], fill="#64748B")
            for x_offset in [0.3, 0.5, 0.7]:
                x = int(w * x_offset)
                draw.line([x, int(h * 0.7), x - 2, int(h * 0.85)], fill="#38BDF8", width=2)
        elif icon_code.startswith("11"):  # Thunder
            # Cloud + Lightning bolt
            draw.ellipse([int(w*0.2), int(h*0.2), int(w*0.8), int(h*0.6)], fill="#475569")
            draw.polygon([
                (int(w*0.5), int(h*0.55)), (int(w*0.42), int(h*0.75)), (int(w*0.52), int(h*0.75)),
                (int(w*0.46), int(h*0.92)), (int(w*0.62), int(h*0.68)), (int(w*0.52), int(h*0.68))
            ], fill="#FACC15")
        elif icon_code.startswith("13"):  # Snow
            # Snowflake
            draw.ellipse([int(w*0.2), int(h*0.25), int(w*0.8), int(h*0.65)], fill="#64748B")
            draw.text((int(w*0.38), int(h*0.65)), "*", fill="#E2E8F0")
        else:  # Mist / Fog
            draw.rounded_rectangle([int(w*0.2), int(h*0.35), int(w*0.8), int(h*0.45)], radius=3, fill="#94A3B8")
            draw.rounded_rectangle([int(w*0.15), int(h*0.5), int(w*0.85), int(h*0.6)], radius=3, fill="#CBD5E1")
            draw.rounded_rectangle([int(w*0.25), int(h*0.65), int(w*0.75), int(h*0.75)], radius=3, fill="#94A3B8")

        return img


# -----------------------------------------------------------------------------
# Helper Utility Functions
# -----------------------------------------------------------------------------
def c_to_f(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return (celsius * 9.0 / 5.0) + 32.0

def f_to_c(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - 32.0) * 5.0 / 9.0

def deg_to_compass(deg: int) -> str:
    """Convert wind direction in degrees to 16-point compass string."""
    val = int((deg / 22.5) + 0.5)
    directions = [
        "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
        "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"
    ]
    return directions[val % 16]

def map_wmo_code(code: int, is_day: bool = True) -> Tuple[str, str, str]:
    """
    Map WMO weather code (used by Open-Meteo) to (Condition, Description, OWM Icon Code).
    """
    d_suffix = "d" if is_day else "n"
    mapping = {
        0: ("Clear", "Clear sky", f"01{d_suffix}"),
        1: ("Mainly Clear", "Mainly clear sky", f"02{d_suffix}"),
        2: ("Partly Cloudy", "Partly cloudy", f"02{d_suffix}"),
        3: ("Overcast", "Overcast skies", f"04{d_suffix}"),
        45: ("Fog", "Foggy conditions", f"50{d_suffix}"),
        48: ("Depositing Rime Fog", "Freezing fog", f"50{d_suffix}"),
        51: ("Drizzle", "Light drizzle", f"09{d_suffix}"),
        53: ("Drizzle", "Moderate drizzle", f"09{d_suffix}"),
        55: ("Drizzle", "Dense drizzle", f"09{d_suffix}"),
        61: ("Rain", "Slight rain", f"10{d_suffix}"),
        63: ("Rain", "Moderate rain", f"10{d_suffix}"),
        65: ("Heavy Rain", "Heavy rain", f"10{d_suffix}"),
        71: ("Snow", "Slight snow fall", f"13{d_suffix}"),
        73: ("Snow", "Moderate snow fall", f"13{d_suffix}"),
        75: ("Snow", "Heavy snow fall", f"13{d_suffix}"),
        77: ("Snow Grains", "Snow grains", f"13{d_suffix}"),
        80: ("Rain Showers", "Slight rain showers", f"09{d_suffix}"),
        81: ("Rain Showers", "Moderate rain showers", f"09{d_suffix}"),
        82: ("Violent Rain Showers", "Violent rain showers", f"09{d_suffix}"),
        85: ("Snow Showers", "Slight snow showers", f"13{d_suffix}"),
        86: ("Snow Showers", "Heavy snow showers", f"13{d_suffix}"),
        95: ("Thunderstorm", "Thunderstorm", f"11{d_suffix}"),
        96: ("Thunderstorm with Hail", "Thunderstorm with slight hail", f"11{d_suffix}"),
        99: ("Thunderstorm with Hail", "Thunderstorm with heavy hail", f"11{d_suffix}"),
    }
    return mapping.get(code, ("Clouds", "Cloudy", f"03{d_suffix}"))
