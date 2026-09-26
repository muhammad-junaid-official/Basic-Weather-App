"""
SkyPulse Weather API — Vercel Serverless Function
Handles weather queries for the web frontend.
Developer / Owner: Muhammad Junaid
"""

import json
import os
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from urllib.request import urlopen
from urllib.error import URLError, HTTPError


DEVELOPER = "Muhammad Junaid"
APP_NAME = "SkyPulse Weather App"


def _fetch_json(url: str, timeout: int = 8) -> dict:
    """Fetch JSON from URL using only stdlib (no requests needed on Vercel)."""
    try:
        with urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raise Exception(f"HTTP {e.code}: {e.reason}")
    except URLError as e:
        raise Exception(f"Network error: {e.reason}")


def _wmo_to_condition(code: int, is_day: bool = True) -> tuple:
    """Map WMO weather code to (condition, description, icon_code)."""
    d = "d" if is_day else "n"
    mapping = {
        0:  ("Clear",           "Clear sky",              f"01{d}"),
        1:  ("Mainly Clear",    "Mainly clear",           f"02{d}"),
        2:  ("Partly Cloudy",   "Partly cloudy",          f"02{d}"),
        3:  ("Overcast",        "Overcast skies",         f"04{d}"),
        45: ("Fog",             "Foggy conditions",       f"50{d}"),
        48: ("Freezing Fog",    "Depositing rime fog",    f"50{d}"),
        51: ("Drizzle",         "Light drizzle",          f"09{d}"),
        53: ("Drizzle",         "Moderate drizzle",       f"09{d}"),
        55: ("Drizzle",         "Dense drizzle",          f"09{d}"),
        61: ("Rain",            "Slight rain",            f"10{d}"),
        63: ("Rain",            "Moderate rain",          f"10{d}"),
        65: ("Heavy Rain",      "Heavy rain",             f"10{d}"),
        71: ("Snow",            "Slight snowfall",        f"13{d}"),
        73: ("Snow",            "Moderate snowfall",      f"13{d}"),
        75: ("Heavy Snow",      "Heavy snowfall",         f"13{d}"),
        77: ("Snow Grains",     "Snow grains",            f"13{d}"),
        80: ("Rain Showers",    "Slight showers",         f"09{d}"),
        81: ("Rain Showers",    "Moderate showers",       f"09{d}"),
        82: ("Rain Showers",    "Violent showers",        f"09{d}"),
        85: ("Snow Showers",    "Slight snow showers",    f"13{d}"),
        86: ("Snow Showers",    "Heavy snow showers",     f"13{d}"),
        95: ("Thunderstorm",    "Thunderstorm",           f"11{d}"),
        96: ("Thunderstorm",    "Thunderstorm with hail", f"11{d}"),
        99: ("Thunderstorm",    "Thunderstorm with hail", f"11{d}"),
    }
    return mapping.get(code, ("Cloudy", "Cloudy skies", f"03{d}"))


def _deg_to_compass(deg: int) -> str:
    directions = ["N","NNE","NE","ENE","E","ESE","SE","SSE","S","SSW","SW","WSW","W","WNW","NW","NNW"]
    return directions[int((deg / 22.5) + 0.5) % 16]


def _c_to_f(c: float) -> float:
    return round((c * 9.0 / 5.0) + 32.0, 1)


def get_weather(city: str, api_key: str = "") -> dict:
    """
    Main weather fetch — uses OpenWeatherMap if API key provided,
    else falls back to Open-Meteo free global weather engine.
    """
    # --- Try OpenWeatherMap if API key is supplied ---
    if api_key:
        try:
            return _fetch_owm(city, api_key)
        except Exception as e:
            if "401" in str(e):
                raise ValueError("Invalid OpenWeatherMap API key.")
            if "404" in str(e):
                raise LookupError(f"City '{city}' not found.")

    # --- Fallback: Geocode then Open-Meteo ---
    from urllib.parse import quote
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={quote(city)}&count=1"
    geo_data = _fetch_json(geo_url)
    results = geo_data.get("results")
    if not results:
        raise LookupError(f"City '{city}' not found. Check the spelling.")

    first = results[0]
    lat = first.get("latitude")
    lon = first.get("longitude")
    city_name = first.get("name", city)
    country = first.get("country_code", first.get("country", ""))

    return _fetch_openmeteo(lat, lon, city_name, country)


def get_location() -> dict:
    """Detect user location via ipinfo.io."""
    try:
        data = _fetch_json("https://ipinfo.io/json", timeout=5)
        loc = data.get("loc", "0,0").split(",")
        return {
            "success": True,
            "city": data.get("city", "London"),
            "country": data.get("country", ""),
            "lat": float(loc[0]) if len(loc) == 2 else 0.0,
            "lon": float(loc[1]) if len(loc) == 2 else 0.0,
        }
    except Exception as e:
        return {"success": False, "city": "London", "error": str(e)}


def _fetch_owm(city: str, api_key: str) -> dict:
    """Fetch from OpenWeatherMap API."""
    from urllib.parse import quote
    curr_url = f"https://api.openweathermap.org/data/2.5/weather?q={quote(city)}&appid={api_key}&units=metric"
    fore_url = f"https://api.openweathermap.org/data/2.5/forecast?q={quote(city)}&appid={api_key}&units=metric"

    curr = _fetch_json(curr_url)
    if curr.get("cod") == 401:
        raise Exception("401 Invalid API key")
    if curr.get("cod") == "404":
        raise Exception("404 City not found")

    forecast_raw = {}
    try:
        forecast_raw = _fetch_json(fore_url)
    except Exception:
        pass

    main = curr.get("main", {})
    w = (curr.get("weather") or [{}])[0]
    wind = curr.get("wind", {})
    sys_ = curr.get("sys", {})

    from datetime import datetime
    temp_c = float(main.get("temp", 0))
    feels_c = float(main.get("feels_like", temp_c))
    sunrise_ts = sys_.get("sunrise", 0)
    sunset_ts = sys_.get("sunset", 0)

    hourly = []
    for item in (forecast_raw.get("list") or [])[:8]:
        dt = datetime.fromtimestamp(item.get("dt", 0))
        m = item.get("main", {})
        iw = (item.get("weather") or [{}])[0]
        tc = float(m.get("temp", 0))
        hourly.append({
            "time": dt.strftime("%I %p").lstrip("0"),
            "temp_c": round(tc, 1),
            "temp_f": _c_to_f(tc),
            "condition": iw.get("main", "Clear"),
            "description": iw.get("description", "").title(),
            "icon_code": iw.get("icon", "01d"),
            "pop": int(float(item.get("pop", 0)) * 100)
        })

    daily_dict = {}
    for item in (forecast_raw.get("list") or []):
        dt = datetime.fromtimestamp(item.get("dt", 0))
        key = dt.strftime("%Y-%m-%d")
        m = item.get("main", {})
        iw = (item.get("weather") or [{}])[0]
        if key not in daily_dict:
            daily_dict[key] = {
                "day": dt.strftime("%a"), "date": dt.strftime("%b %d"),
                "min_c": float(m.get("temp_min", 0)),
                "max_c": float(m.get("temp_max", 0)),
                "condition": iw.get("main", "Clear"),
                "description": iw.get("description", "").title(),
                "icon_code": iw.get("icon", "01d")
            }
        else:
            daily_dict[key]["min_c"] = min(daily_dict[key]["min_c"], float(m.get("temp_min", 0)))
            daily_dict[key]["max_c"] = max(daily_dict[key]["max_c"], float(m.get("temp_max", 0)))

    daily = []
    for _, d in list(daily_dict.items())[:5]:
        d["min_f"] = _c_to_f(d["min_c"])
        d["max_f"] = _c_to_f(d["max_c"])
        d["min_c"] = round(d["min_c"], 1)
        d["max_c"] = round(d["max_c"], 1)
        daily.append(d)

    wind_ms = float(wind.get("speed", 0))
    return {
        "city": curr.get("name", city),
        "country": sys_.get("country", ""),
        "lat": curr.get("coord", {}).get("lat", 0),
        "lon": curr.get("coord", {}).get("lon", 0),
        "temp_c": round(temp_c, 1),
        "temp_f": _c_to_f(temp_c),
        "feels_like_c": round(feels_c, 1),
        "feels_like_f": _c_to_f(feels_c),
        "temp_min_c": round(float(main.get("temp_min", temp_c)), 1),
        "temp_min_f": _c_to_f(float(main.get("temp_min", temp_c))),
        "temp_max_c": round(float(main.get("temp_max", temp_c)), 1),
        "temp_max_f": _c_to_f(float(main.get("temp_max", temp_c))),
        "humidity": int(main.get("humidity", 0)),
        "pressure": int(main.get("pressure", 1013)),
        "wind_speed_ms": round(wind_ms, 1),
        "wind_speed_kmh": round(wind_ms * 3.6, 1),
        "wind_speed_mph": round(wind_ms * 2.23694, 1),
        "wind_dir": _deg_to_compass(int(wind.get("deg", 0))),
        "visibility_km": round(curr.get("visibility", 10000) / 1000, 1),
        "visibility_mi": round(curr.get("visibility", 10000) / 1609.34, 1),
        "sunrise": datetime.fromtimestamp(sunrise_ts).strftime("%I:%M %p") if sunrise_ts else "N/A",
        "sunset": datetime.fromtimestamp(sunset_ts).strftime("%I:%M %p") if sunset_ts else "N/A",
        "condition": w.get("main", "Clear"),
        "description": w.get("description", "Clear sky").title(),
        "icon_code": w.get("icon", "01d"),
        "updated_time": datetime.now().strftime("%I:%M %p"),
        "source": "OpenWeatherMap API",
        "hourly": hourly,
        "daily": daily
    }


def _fetch_openmeteo(lat, lon, city_name, country) -> dict:
    """Fetch from Open-Meteo (no API key required)."""
    from datetime import datetime
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
        "weather_code,surface_pressure,wind_speed_10m,wind_direction_10m"
        "&hourly=temperature_2m,relative_humidity_2m,precipitation_probability,weather_code"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,sunrise,sunset"
        "&timezone=auto"
    )
    data = _fetch_json(url)
    curr = data.get("current", {})

    temp_c = float(curr.get("temperature_2m", 0))
    feels_c = float(curr.get("apparent_temperature", temp_c))
    humidity = int(curr.get("relative_humidity_2m", 0))
    wcode = int(curr.get("weather_code", 0))
    is_day = bool(curr.get("is_day", 1))
    wind_kmh = float(curr.get("wind_speed_10m", 0))
    wind_ms = round(wind_kmh / 3.6, 1)
    wind_deg = int(curr.get("wind_direction_10m", 0))
    pressure = int(curr.get("surface_pressure", 1013))
    cond, desc, icon = _wmo_to_condition(wcode, is_day)

    daily_raw = data.get("daily", {})
    daily_times = daily_raw.get("time", [])
    daily_max = daily_raw.get("temperature_2m_max", [])
    daily_min = daily_raw.get("temperature_2m_min", [])
    daily_codes = daily_raw.get("weather_code", [])
    sunrises = daily_raw.get("sunrise", [])
    sunsets = daily_raw.get("sunset", [])

    sunrise_str = "N/A"
    sunset_str = "N/A"
    try:
        if sunrises:
            sunrise_str = datetime.fromisoformat(sunrises[0]).strftime("%I:%M %p")
        if sunsets:
            sunset_str = datetime.fromisoformat(sunsets[0]).strftime("%I:%M %p")
    except Exception:
        pass

    daily = []
    for i in range(min(5, len(daily_times))):
        try:
            dt_obj = datetime.fromisoformat(daily_times[i])
            day_name = dt_obj.strftime("%a")
            date_str = dt_obj.strftime("%b %d")
        except Exception:
            day_name, date_str = f"Day{i}", ""
        dmax = round(float(daily_max[i]), 1) if i < len(daily_max) else temp_c
        dmin = round(float(daily_min[i]), 1) if i < len(daily_min) else temp_c
        dc, dd, di = _wmo_to_condition(int(daily_codes[i]) if i < len(daily_codes) else 0, True)
        daily.append({
            "day": day_name, "date": date_str,
            "min_c": dmin, "min_f": _c_to_f(dmin),
            "max_c": dmax, "max_f": _c_to_f(dmax),
            "condition": dc, "description": dd, "icon_code": di
        })

    hourly_raw = data.get("hourly", {})
    h_times = hourly_raw.get("time", [])
    h_temps = hourly_raw.get("temperature_2m", [])
    h_codes = hourly_raw.get("weather_code", [])
    h_pops = hourly_raw.get("precipitation_probability", [])

    now_prefix = datetime.now().strftime("%Y-%m-%dT%H")
    start_idx = next((i for i, t in enumerate(h_times) if t.startswith(now_prefix)), 0)

    hourly = []
    for i in range(start_idx, min(start_idx + 8, len(h_times))):
        try:
            hdt = datetime.fromisoformat(h_times[i])
            htime = hdt.strftime("%I %p").lstrip("0")
        except Exception:
            htime = f"+{i - start_idx}h"
        hc = round(float(h_temps[i]), 1) if i < len(h_temps) else temp_c
        hcode = int(h_codes[i]) if i < len(h_codes) else 0
        hcond, hdesc, hicon = _wmo_to_condition(hcode, True)
        pop = int(h_pops[i]) if i < len(h_pops) and h_pops[i] is not None else 0
        hourly.append({
            "time": htime,
            "temp_c": hc, "temp_f": _c_to_f(hc),
            "condition": hcond, "description": hdesc, "icon_code": hicon, "pop": pop
        })

    t_min_c = daily[0]["min_c"] if daily else temp_c
    t_max_c = daily[0]["max_c"] if daily else temp_c

    return {
        "city": city_name,
        "country": country,
        "lat": lat, "lon": lon,
        "temp_c": round(temp_c, 1),
        "temp_f": _c_to_f(temp_c),
        "feels_like_c": round(feels_c, 1),
        "feels_like_f": _c_to_f(feels_c),
        "temp_min_c": round(t_min_c, 1), "temp_min_f": _c_to_f(t_min_c),
        "temp_max_c": round(t_max_c, 1), "temp_max_f": _c_to_f(t_max_c),
        "humidity": humidity,
        "pressure": pressure,
        "wind_speed_ms": wind_ms,
        "wind_speed_kmh": round(wind_kmh, 1),
        "wind_speed_mph": round(wind_ms * 2.23694, 1),
        "wind_dir": _deg_to_compass(wind_deg),
        "visibility_km": 10.0, "visibility_mi": 6.2,
        "sunrise": sunrise_str, "sunset": sunset_str,
        "condition": cond, "description": desc, "icon_code": icon,
        "updated_time": datetime.now().strftime("%I:%M %p"),
        "source": "Open-Meteo Free API",
        "hourly": hourly,
        "daily": daily
    }


# ─── Vercel Serverless Handler ───────────────────────────────────────────────

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path.rstrip("/")

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

        try:
            if path.endswith("/locate"):
                result = get_location()
                self.wfile.write(json.dumps(result).encode())
                return

            city = (params.get("city") or params.get("q") or [None])[0]
            api_key = (params.get("key") or params.get("apikey") or [""])[0]

            owm_env_key = os.environ.get("OPENWEATHERMAP_API_KEY", "")
            effective_key = api_key or owm_env_key

            if not city:
                self.wfile.write(json.dumps({
                    "error": "Missing parameter: city",
                    "usage": "/api/weather?city=London",
                    "developer": DEVELOPER
                }).encode())
                return

            data = get_weather(city, effective_key)
            data["developer"] = DEVELOPER
            data["app"] = APP_NAME
            self.wfile.write(json.dumps(data).encode())

        except LookupError as e:
            self.wfile.write(json.dumps({"error": str(e), "type": "city_not_found"}).encode())
        except ValueError as e:
            self.wfile.write(json.dumps({"error": str(e), "type": "invalid_key"}).encode())
        except Exception as e:
            self.wfile.write(json.dumps({"error": str(e), "type": "server_error"}).encode())

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def log_message(self, format, *args):
        pass
