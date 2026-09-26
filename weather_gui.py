"""
SkyPulse Weather App - Advanced Tier GUI
Modern, authentic graphical weather interface built with Tkinter & Pillow.

Features:
- GUI window with city input field, 'Get Weather' button, and results panel
- Dynamic weather condition icons fetched from OpenWeatherMap CDN with offline fallbacks
- Hourly forecast panel (next 6-12 hours) with precipitation probability
- Daily forecast panel (next 5 days) with min/max temperature visualizers
- Unit toggle (°C / °F) with instant recalculation
- Automatic location detection via ipinfo.io
- Elegant in-app notification & error banner (no terminal prints)
- Asynchronous threaded API requests (zero GUI freezing)
- OpenWeatherMap API Key settings modal with persistent configuration
- Developer / Owner attribution: Muhammad Junaid

Developer: Muhammad Junaid
"""

import sys
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any, List
from datetime import datetime
from PIL import Image, ImageTk

from config import (
    DEVELOPER_NAME,
    APP_NAME,
    APP_VERSION,
    REPO_URL,
    load_config,
    save_config,
    ICONS_DIR
)
from weather_service import (
    WeatherService,
    CityNotFoundError,
    InvalidApiKeyError,
    RateLimitError,
    NetworkError,
    ValidationError,
    WeatherAppError
)

# Enable DPI Awareness on Windows
if sys.platform.startswith("win"):
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# Color Palette (Modern Deep Slate & Electric Sky Blue)
COLORS = {
    "bg": "#0B132B",            # Main Window Background
    "header_bg": "#1C2541",     # Top Nav / Header
    "card_bg": "#1E293B",       # Main Cards Background
    "card_border": "#334155",   # Card Border Outline
    "card_hover": "#273549",    # Card Hover State
    "primary": "#38BDF8",       # Sky Blue Accent
    "primary_hover": "#0284C7", # Darker Sky Blue
    "secondary": "#475569",     # Slate Gray
    "text_main": "#F8FAFC",     # Crisp White Text
    "text_muted": "#94A3B8",    # Muted Slate Text
    "text_dim": "#64748B",      # Dim helper text
    "accent_gold": "#FBBF24",   # Warm Sun Gold
    "accent_green": "#10B981",  # Fresh emerald
    "error_bg": "#451A1A",      # Error Banner Dark Red
    "error_border": "#EF4444",  # Error Red Border
    "error_text": "#FCA5A5",    # Error Soft Text
    "info_bg": "#172554",       # Info Banner Dark Blue
    "info_border": "#3B82F6",   # Info Border
    "info_text": "#BFDBFE",     # Info Text
    "input_bg": "#0F172A",      # Input Box Background
    "input_border": "#334155",  # Input Border
}

FONTS = {
    "title": ("Segoe UI", 16, "bold"),
    "subtitle": ("Segoe UI", 10),
    "city": ("Segoe UI", 24, "bold"),
    "temp_hero": ("Segoe UI", 48, "bold"),
    "condition": ("Segoe UI", 13, "bold"),
    "meta": ("Segoe UI", 10),
    "heading": ("Segoe UI", 12, "bold"),
    "card_val": ("Segoe UI", 14, "bold"),
    "card_lbl": ("Segoe UI", 9),
    "btn": ("Segoe UI", 10, "bold"),
    "input": ("Segoe UI", 11),
    "small": ("Segoe UI", 8),
}


class ModernButton(tk.Canvas):
    """Custom rounded, smooth hover-effect button."""
    def __init__(self, parent, text, command=None, bg_color="#38BDF8", hover_color="#0284C7",
                 text_color="#0B132B", width=120, height=36, radius=10, font=FONTS["btn"]):
        super().__init__(parent, width=width, height=height, bg=parent["bg"],
                         highlightthickness=0, cursor="hand2")
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text_color = text_color
        self.radius = radius
        self.btn_text = text
        self.btn_font = font
        self.is_hovered = False
        self.is_disabled = False

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_reqwidth()
        h = self.winfo_reqheight()
        fill_color = self.hover_color if self.is_hovered else self.bg_color
        if self.is_disabled:
            fill_color = "#334155"

        # Rounded rectangle
        r = self.radius
        self.create_arc((0, 0, 2*r, 2*r), start=90, extent=90, fill=fill_color, outline=fill_color)
        self.create_arc((w - 2*r, 0, w, 2*r), start=0, extent=90, fill=fill_color, outline=fill_color)
        self.create_arc((w - 2*r, h - 2*r, w, h), start=270, extent=90, fill=fill_color, outline=fill_color)
        self.create_arc((0, h - 2*r, 2*r, h), start=180, extent=90, fill=fill_color, outline=fill_color)
        self.create_rectangle((r, 0, w - r, h), fill=fill_color, outline=fill_color)
        self.create_rectangle((0, r, w, h - r), fill=fill_color, outline=fill_color)

        t_color = "#94A3B8" if self.is_disabled else self.text_color
        self.create_text(w // 2, h // 2, text=self.btn_text, fill=t_color, font=self.btn_font)

    def set_text(self, text):
        self.btn_text = text
        self._draw()

    def set_disabled(self, disabled: bool):
        self.is_disabled = disabled
        self.config(cursor="arrow" if disabled else "hand2")
        self._draw()

    def _on_enter(self, _):
        if not self.is_disabled:
            self.is_hovered = True
            self._draw()

    def _on_leave(self, _):
        if not self.is_disabled:
            self.is_hovered = False
            self._draw()

    def _on_click(self, _):
        if not self.is_disabled and self.command:
            self.command()


class WeatherAppGUI(tk.Tk):
    """Main Weather Application GUI Window."""

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} • Developed by {DEVELOPER_NAME}")
        self.geometry("980x790")
        self.minsize(860, 680)
        self.configure(bg=COLORS["bg"])

        # State & Configuration
        self.config_data = load_config()
        self.current_unit = self.config_data.get("unit", "metric")  # 'metric' (°C) or 'imperial' (°F)
        self.weather_service = WeatherService(api_key=self.config_data.get("owm_api_key", ""))
        self.current_weather_data: Optional[Dict[str, Any]] = None
        self.image_references: List[Any] = []
        self.is_loading = False

        self._build_ui()
        
        # Initial Weather Load
        last_city = self.config_data.get("last_city", "London")
        if self.config_data.get("auto_detect_location", True):
            self.after(200, self.auto_detect_location)
        else:
            self.after(200, lambda: self.fetch_weather_async(last_city))

    def _build_ui(self):
        # -------------------------------------------------------------
        # Header Navbar
        # -------------------------------------------------------------
        self.header_frame = tk.Frame(self, bg=COLORS["header_bg"], height=64)
        self.header_frame.pack(side="top", fill="x")
        self.header_frame.pack_propagate(False)

        # Brand / App Title
        brand_frame = tk.Frame(self.header_frame, bg=COLORS["header_bg"])
        brand_frame.pack(side="left", padx=20, pady=12)

        lbl_app = tk.Label(
            brand_frame,
            text="🌤️  SkyPulse Weather",
            font=FONTS["title"],
            bg=COLORS["header_bg"],
            fg=COLORS["text_main"]
        )
        lbl_app.pack(side="left")

        # Developer Badge
        dev_badge = tk.Label(
            brand_frame,
            text=f"by {DEVELOPER_NAME}",
            font=FONTS["subtitle"],
            bg=COLORS["header_bg"],
            fg=COLORS["primary"]
        )
        dev_badge.pack(side="left", padx=(10, 0), pady=(3, 0))

        # Right Controls: Source Status, Unit Toggle, Settings
        right_frame = tk.Frame(self.header_frame, bg=COLORS["header_bg"])
        right_frame.pack(side="right", padx=20, pady=12)

        self.lbl_api_status = tk.Label(
            right_frame,
            text="● Live API Active",
            font=FONTS["meta"],
            bg=COLORS["header_bg"],
            fg=COLORS["accent_green"]
        )
        self.lbl_api_status.pack(side="left", padx=10)

        # Unit Toggle Button
        self.btn_unit_toggle = ModernButton(
            right_frame,
            text="°C  |  °F",
            command=self.toggle_unit,
            bg_color="#334155",
            hover_color="#475569",
            text_color=COLORS["text_main"],
            width=76,
            height=32,
            radius=6
        )
        self.btn_unit_toggle.pack(side="left", padx=6)

        # API Key Settings Button
        self.btn_settings = ModernButton(
            right_frame,
            text="⚙️ API Key",
            command=self.open_settings_dialog,
            bg_color="#334155",
            hover_color="#475569",
            text_color=COLORS["text_main"],
            width=90,
            height=32,
            radius=6
        )
        self.btn_settings.pack(side="left", padx=6)

        self._update_api_status_badge()

        # -------------------------------------------------------------
        # Search & Actions Bar
        # -------------------------------------------------------------
        search_container = tk.Frame(self, bg=COLORS["bg"])
        search_container.pack(fill="x", padx=24, pady=(16, 8))

        # Search Input Box with rounded appearance
        input_wrapper = tk.Frame(search_container, bg=COLORS["input_bg"], highlightbackground=COLORS["input_border"], highlightthickness=1)
        input_wrapper.pack(side="left", fill="x", expand=True, ipady=4)

        search_icon = tk.Label(input_wrapper, text="🔍", font=("Segoe UI", 11), bg=COLORS["input_bg"], fg=COLORS["text_muted"])
        search_icon.pack(side="left", padx=(10, 4))

        self.city_entry = tk.Entry(
            input_wrapper,
            font=FONTS["input"],
            bg=COLORS["input_bg"],
            fg=COLORS["text_main"],
            insertbackground=COLORS["primary"],
            relief="flat",
            borderwidth=0
        )
        self.city_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.city_entry.bind("<Return>", lambda _: self.on_search_click())

        # Placeholder text helper
        self.city_entry.insert(0, self.config_data.get("last_city", "London"))
        self.city_entry.bind("<FocusIn>", self._clear_placeholder)

        # "Get Weather" Button
        self.btn_search = ModernButton(
            search_container,
            text="Get Weather",
            command=self.on_search_click,
            bg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color="#0B132B",
            width=115,
            height=38,
            radius=8
        )
        self.btn_search.pack(side="left", padx=(12, 6))

        # "Locate Me" Button
        self.btn_locate = ModernButton(
            search_container,
            text="📍 Locate Me",
            command=self.auto_detect_location,
            bg_color="#1E293B",
            hover_color="#334155",
            text_color=COLORS["primary"],
            width=105,
            height=38,
            radius=8
        )
        self.btn_locate.pack(side="left", padx=4)

        # Quick City Pills
        chips_frame = tk.Frame(self, bg=COLORS["bg"])
        chips_frame.pack(fill="x", padx=24, pady=(2, 10))

        quick_label = tk.Label(chips_frame, text="Popular:", font=FONTS["small"], bg=COLORS["bg"], fg=COLORS["text_dim"])
        quick_label.pack(side="left", padx=(0, 6))

        for city_name in ["London", "New York", "Tokyo", "Paris", "Dubai", "Lahore", "Sydney"]:
            chip = tk.Label(
                chips_frame,
                text=city_name,
                font=FONTS["small"],
                bg=COLORS["card_bg"],
                fg=COLORS["text_muted"],
                padx=8,
                pady=2,
                cursor="hand2"
            )
            chip.pack(side="left", padx=3)
            chip.bind("<Button-1>", lambda e, c=city_name: self.on_quick_city_click(c))
            chip.bind("<Enter>", lambda e, w=chip: w.config(bg="#334155", fg=COLORS["primary"]))
            chip.bind("<Leave>", lambda e, w=chip: w.config(bg=COLORS["card_bg"], fg=COLORS["text_muted"]))

        # -------------------------------------------------------------
        # In-App Notification / Error Banner
        # -------------------------------------------------------------
        self.banner_frame = tk.Frame(self, bg=COLORS["error_bg"], highlightbackground=COLORS["error_border"], highlightthickness=1)
        # Note: Packed dynamically when an error occurs
        
        self.lbl_banner_icon = tk.Label(self.banner_frame, text="⚠️", font=("Segoe UI", 12), bg=COLORS["error_bg"])
        self.lbl_banner_icon.pack(side="left", padx=(12, 6), pady=8)

        self.lbl_banner_text = tk.Label(
            self.banner_frame,
            text="",
            font=FONTS["meta"],
            bg=COLORS["error_bg"],
            fg=COLORS["error_text"],
            wraplength=700,
            justify="left"
        )
        self.lbl_banner_text.pack(side="left", fill="x", expand=True, pady=8)

        self.btn_banner_close = tk.Label(
            self.banner_frame,
            text="✕",
            font=("Segoe UI", 11, "bold"),
            bg=COLORS["error_bg"],
            fg=COLORS["error_text"],
            cursor="hand2"
        )
        self.btn_banner_close.pack(side="right", padx=12, pady=8)
        self.btn_banner_close.bind("<Button-1>", lambda _: self.hide_banner())

        # -------------------------------------------------------------
        # Main Scrollable / Responsive Content Body
        # -------------------------------------------------------------
        self.main_body = tk.Frame(self, bg=COLORS["bg"])
        self.main_body.pack(fill="both", expand=True, padx=24, pady=4)

        # Upper Section: Hero Card (Left) + Detailed Metrics Grid (Right)
        top_section = tk.Frame(self.main_body, bg=COLORS["bg"])
        top_section.pack(fill="x", expand=False, pady=(0, 12))

        # --- Hero Weather Card ---
        self.hero_card = tk.Frame(
            top_section,
            bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
            padx=20,
            pady=18
        )
        self.hero_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Hero Top Info: Location & Updated
        hero_meta_frame = tk.Frame(self.hero_card, bg=COLORS["card_bg"])
        hero_meta_frame.pack(fill="x")

        self.lbl_location = tk.Label(
            hero_meta_frame,
            text="Loading Location...",
            font=FONTS["city"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_main"],
            anchor="w"
        )
        self.lbl_location.pack(side="left")

        self.lbl_updated = tk.Label(
            hero_meta_frame,
            text="",
            font=FONTS["small"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_dim"],
            anchor="e"
        )
        self.lbl_updated.pack(side="right", pady=(8, 0))

        # Hero Mid: Big Icon + Temperature + Condition
        hero_mid_frame = tk.Frame(self.hero_card, bg=COLORS["card_bg"])
        hero_mid_frame.pack(fill="x", pady=(10, 6))

        self.lbl_weather_icon = tk.Label(hero_mid_frame, bg=COLORS["card_bg"])
        self.lbl_weather_icon.pack(side="left", padx=(0, 16))

        temp_col = tk.Frame(hero_mid_frame, bg=COLORS["card_bg"])
        temp_col.pack(side="left", fill="y")

        self.lbl_temperature = tk.Label(
            temp_col,
            text="--°",
            font=FONTS["temp_hero"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_main"]
        )
        self.lbl_temperature.pack(anchor="w")

        self.lbl_condition = tk.Label(
            temp_col,
            text="Fetching forecast...",
            font=FONTS["condition"],
            bg=COLORS["card_bg"],
            fg=COLORS["primary"]
        )
        self.lbl_condition.pack(anchor="w")

        # Hero Bottom: High / Low / Feels Like
        self.lbl_hero_sub = tk.Label(
            self.hero_card,
            text="",
            font=FONTS["meta"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_muted"]
        )
        self.lbl_hero_sub.pack(anchor="w", pady=(6, 0))

        # --- Detailed Metrics Grid (Right Panel) ---
        self.metrics_card = tk.Frame(
            top_section,
            bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
            padx=16,
            pady=16
        )
        self.metrics_card.pack(side="right", fill="both", expand=True, padx=(8, 0))

        lbl_metrics_title = tk.Label(
            self.metrics_card,
            text="Weather Details & Metrics",
            font=FONTS["heading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_main"]
        )
        lbl_metrics_title.pack(anchor="w", pady=(0, 10))

        self.grid_frame = tk.Frame(self.metrics_card, bg=COLORS["card_bg"])
        self.grid_frame.pack(fill="both", expand=True)

        self.metric_widgets = {}
        metrics_specs = [
            ("humidity", "💧 Humidity", "--%"),
            ("wind", "💨 Wind Speed", "--"),
            ("pressure", "🧭 Pressure", "-- hPa"),
            ("visibility", "👁️ Visibility", "-- km"),
            ("sunrise", "🌅 Sunrise", "--:--"),
            ("sunset", "🌇 Sunset", "--:--"),
        ]

        for idx, (key, label_text, default_val) in enumerate(metrics_specs):
            row = idx // 2
            col = idx % 2

            m_box = tk.Frame(self.grid_frame, bg="#162032", padx=10, pady=8, highlightbackground="#233149", highlightthickness=1)
            m_box.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            self.grid_frame.grid_columnconfigure(col, weight=1)
            self.grid_frame.grid_rowconfigure(row, weight=1)

            lbl = tk.Label(m_box, text=label_text, font=FONTS["card_lbl"], bg="#162032", fg=COLORS["text_dim"])
            lbl.pack(anchor="w")

            val = tk.Label(m_box, text=default_val, font=FONTS["card_val"], bg="#162032", fg=COLORS["text_main"])
            val.pack(anchor="w", pady=(2, 0))

            self.metric_widgets[key] = val

        # -------------------------------------------------------------
        # Lower Section: Hourly Forecast (Top) & 5-Day Daily Forecast (Bottom)
        # -------------------------------------------------------------
        bottom_notebook_frame = tk.Frame(self.main_body, bg=COLORS["bg"])
        bottom_notebook_frame.pack(fill="both", expand=True)

        # Hourly Forecast Card
        self.hourly_frame = tk.Frame(
            bottom_notebook_frame,
            bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
            padx=14,
            pady=12
        )
        self.hourly_frame.pack(fill="x", pady=(0, 10))

        lbl_hourly_heading = tk.Label(
            self.hourly_frame,
            text="⏱️ Hourly Forecast (Next 6 - 12 Hours)",
            font=FONTS["heading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_main"]
        )
        lbl_hourly_heading.pack(anchor="w", pady=(0, 8))

        self.hourly_strip = tk.Frame(self.hourly_frame, bg=COLORS["card_bg"])
        self.hourly_strip.pack(fill="x")

        # 5-Day Daily Forecast Card
        self.daily_frame = tk.Frame(
            bottom_notebook_frame,
            bg=COLORS["card_bg"],
            highlightbackground=COLORS["card_border"],
            highlightthickness=1,
            padx=14,
            pady=12
        )
        self.daily_frame.pack(fill="both", expand=True)

        lbl_daily_heading = tk.Label(
            self.daily_frame,
            text="📅 5-Day Extended Weather Forecast",
            font=FONTS["heading"],
            bg=COLORS["card_bg"],
            fg=COLORS["text_main"]
        )
        lbl_daily_heading.pack(anchor="w", pady=(0, 8))

        self.daily_strip = tk.Frame(self.daily_frame, bg=COLORS["card_bg"])
        self.daily_strip.pack(fill="both", expand=True)

        # -------------------------------------------------------------
        # Footer
        # -------------------------------------------------------------
        footer_frame = tk.Frame(self, bg=COLORS["bg"], height=28)
        footer_frame.pack(side="bottom", fill="x", pady=(4, 6))

        lbl_footer = tk.Label(
            footer_frame,
            text=f"Crafted with 💙 by {DEVELOPER_NAME}  •  OpenWeatherMap & Live Global Engine",
            font=FONTS["small"],
            bg=COLORS["bg"],
            fg=COLORS["text_dim"]
        )
        lbl_footer.pack()

    # -----------------------------------------------------------------
    # In-App Banner Management (Error & Info Notifications)
    # -----------------------------------------------------------------
    def show_banner(self, message: str, is_error: bool = True):
        """Displays error or info messages directly in the GUI without intrusive popups."""
        bg_color = COLORS["error_bg"] if is_error else COLORS["info_bg"]
        border_color = COLORS["error_border"] if is_error else COLORS["info_border"]
        text_color = COLORS["error_text"] if is_error else COLORS["info_text"]
        icon_str = "❌ " if is_error else "ℹ️ "

        self.banner_frame.configure(bg=bg_color, highlightbackground=border_color)
        self.lbl_banner_icon.configure(text=icon_str, bg=bg_color)
        self.lbl_banner_text.configure(text=message, bg=bg_color, fg=text_color)
        self.btn_banner_close.configure(bg=bg_color, fg=text_color)

        self.banner_frame.pack(fill="x", padx=24, pady=(0, 8), before=self.main_body)

    def hide_banner(self):
        """Hides the in-app banner."""
        self.banner_frame.pack_forget()

    # -----------------------------------------------------------------
    # Search and Async Fetch
    # -----------------------------------------------------------------
    def _clear_placeholder(self, _):
        if self.city_entry.get() == "Enter city name or ZIP code...":
            self.city_entry.delete(0, tk.END)

    def on_quick_city_click(self, city_name: str):
        self.city_entry.delete(0, tk.END)
        self.city_entry.insert(0, city_name)
        self.fetch_weather_async(city_name)

    def on_search_click(self):
        query = self.city_entry.get().strip()
        if not query:
            self.show_banner("Please enter a valid city name or ZIP code.", is_error=True)
            return
        self.fetch_weather_async(query)

    def auto_detect_location(self):
        """Auto detects user location via ipinfo.io."""
        if self.is_loading:
            return
        self._set_loading_state(True, "Detecting your location...")
        self.hide_banner()

        def worker():
            res = self.weather_service.detect_user_location()
            if res.get("success"):
                city = res.get("city", "London")
                self.after(0, self._on_location_detected, city)
            else:
                self.after(0, self._on_location_detect_failed, res.get("error", "Failed to detect location"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_location_detected(self, city: str):
        self.city_entry.delete(0, tk.END)
        self.city_entry.insert(0, city)
        self.fetch_weather_async(city)

    def _on_location_detect_failed(self, error_msg: str):
        self._set_loading_state(False)
        self.show_banner(f"Could not auto-detect location: {error_msg}. Using London as fallback.", is_error=False)
        self.fetch_weather_async("London")

    def fetch_weather_async(self, query: str):
        """Asynchronously queries weather data without blocking the UI thread."""
        if self.is_loading:
            return

        query = query.strip()
        if not query:
            self.show_banner("Input cannot be empty. Please enter a city or ZIP code.", is_error=True)
            return

        self._set_loading_state(True, f"Fetching weather for '{query}'...")
        self.hide_banner()

        def worker():
            try:
                data = self.weather_service.fetch_weather(query)
                self.after(0, self._on_weather_success, data)
            except CityNotFoundError as e:
                self.after(0, self._on_weather_error, str(e), "city")
            except InvalidApiKeyError as e:
                self.after(0, self._on_weather_error, str(e), "key")
            except RateLimitError as e:
                self.after(0, self._on_weather_error, str(e), "rate")
            except NetworkError as e:
                self.after(0, self._on_weather_error, str(e), "network")
            except Exception as e:
                self.after(0, self._on_weather_error, f"Error: {str(e)}", "general")

        threading.Thread(target=worker, daemon=True).start()

    def _set_loading_state(self, loading: bool, message: str = ""):
        self.is_loading = loading
        self.btn_search.set_disabled(loading)
        self.btn_locate.set_disabled(loading)
        if loading:
            self.lbl_condition.config(text=message, fg=COLORS["accent_gold"])
        else:
            self.btn_search.set_text("Get Weather")

    def _on_weather_success(self, data: Dict[str, Any]):
        self._set_loading_state(False)
        self.current_weather_data = data
        self.config_data["last_city"] = data.get("city", "London")
        save_config(self.config_data)

        self._render_current_weather(data)
        self._render_hourly_forecast(data.get("hourly", []))
        self._render_daily_forecast(data.get("daily", []))
        self._update_api_status_badge()

    def _on_weather_error(self, message: str, error_type: str):
        self._set_loading_state(False)
        self.lbl_condition.config(text="Forecast unavailable", fg=COLORS["error_text"])

        if error_type == "key":
            msg = f"{message} (Click '⚙️ API Key' above to update your key or clear it for Free Global API)."
        elif error_type == "city":
            msg = f"{message} Check spelling or try including country code (e.g. 'Paris, FR' or '90210, US')."
        else:
            msg = message

        self.show_banner(msg, is_error=True)

    # -----------------------------------------------------------------
    # Rendering Methods
    # -----------------------------------------------------------------
    def _render_current_weather(self, data: Dict[str, Any]):
        city = data.get("city", "Unknown")
        country = data.get("country", "")
        loc_str = f"{city}, {country}" if country else city
        self.lbl_location.config(text=loc_str)

        # Updated time
        updated = data.get("updated_time", "")
        source = data.get("source", "")
        self.lbl_updated.config(text=f"Report: {updated} • {source}")

        # Unit-based temperature display
        is_metric = (self.current_unit == "metric")
        temp = data.get("temp_c" if is_metric else "temp_f", 0.0)
        unit_str = "°C" if is_metric else "°F"
        self.lbl_temperature.config(text=f"{round(temp)}{unit_str}")

        # Condition & Description
        desc = data.get("description", "Clear")
        self.lbl_condition.config(text=desc, fg=COLORS["primary"])

        # Sub details
        feels = data.get("feels_like_c" if is_metric else "feels_like_f", 0.0)
        max_t = data.get("temp_max_c" if is_metric else "temp_max_f", 0.0)
        min_t = data.get("temp_min_c" if is_metric else "temp_min_f", 0.0)
        self.lbl_hero_sub.config(
            text=f"Feels like {round(feels)}{unit_str}   •   High: {round(max_t)}{unit_str}   •   Low: {round(min_t)}{unit_str}"
        )

        # Weather Icon
        icon_code = data.get("icon_code", "01d")
        icon_img = self.weather_service.get_weather_icon(icon_code, size=(90, 90))
        if icon_img:
            tk_img = ImageTk.PhotoImage(icon_img)
            self.image_references.append(tk_img)
            self.lbl_weather_icon.config(image=tk_img)
            self.lbl_weather_icon.image = tk_img

        # Detailed Metrics
        self.metric_widgets["humidity"].config(text=f"{data.get('humidity', 0)}%")
        wind_val = data.get("wind_speed_kmh" if is_metric else "wind_speed_mph", 0.0)
        wind_unit = "km/h" if is_metric else "mph"
        wind_dir = data.get("wind_dir", "")
        self.metric_widgets["wind"].config(text=f"{wind_val} {wind_unit} ({wind_dir})")
        self.metric_widgets["pressure"].config(text=f"{data.get('pressure', 1013)} hPa")
        
        vis_val = data.get("visibility_km" if is_metric else "visibility_mi", 0.0)
        vis_unit = "km" if is_metric else "mi"
        self.metric_widgets["visibility"].config(text=f"{vis_val} {vis_unit}")
        self.metric_widgets["sunrise"].config(text=str(data.get("sunrise", "N/A")))
        self.metric_widgets["sunset"].config(text=str(data.get("sunset", "N/A")))

    def _render_hourly_forecast(self, hourly: List[Dict[str, Any]]):
        for widget in self.hourly_strip.winfo_children():
            widget.destroy()

        if not hourly:
            lbl_empty = tk.Label(self.hourly_strip, text="Hourly forecast data not available.", font=FONTS["meta"], bg=COLORS["card_bg"], fg=COLORS["text_dim"])
            lbl_empty.pack(pady=10)
            return

        is_metric = (self.current_unit == "metric")
        unit_str = "°C" if is_metric else "°F"

        # Show next 6 to 8 forecast intervals
        for item in hourly[:7]:
            h_card = tk.Frame(self.hourly_strip, bg="#162032", highlightbackground="#233149", highlightthickness=1, padx=10, pady=8)
            h_card.pack(side="left", fill="both", expand=True, padx=3)

            lbl_time = tk.Label(h_card, text=item.get("time", ""), font=FONTS["card_lbl"], bg="#162032", fg=COLORS["text_muted"])
            lbl_time.pack()

            # Small Icon
            icon_img = self.weather_service.get_weather_icon(item.get("icon_code", "01d"), size=(36, 36))
            if icon_img:
                tk_icon = ImageTk.PhotoImage(icon_img)
                self.image_references.append(tk_icon)
                lbl_icon = tk.Label(h_card, image=tk_icon, bg="#162032")
                lbl_icon.image = tk_icon
                lbl_icon.pack(pady=2)

            # Temp
            t_val = item.get("temp_c" if is_metric else "temp_f", 0.0)
            lbl_temp = tk.Label(h_card, text=f"{round(t_val)}{unit_str}", font=FONTS["card_val"], bg="#162032", fg=COLORS["text_main"])
            lbl_temp.pack()

            # Rain probability badge
            pop = item.get("pop", 0)
            pop_color = COLORS["primary"] if pop > 30 else COLORS["text_dim"]
            lbl_pop = tk.Label(h_card, text=f"💧 {pop}%", font=FONTS["small"], bg="#162032", fg=pop_color)
            lbl_pop.pack(pady=(2, 0))

    def _render_daily_forecast(self, daily: List[Dict[str, Any]]):
        for widget in self.daily_strip.winfo_children():
            widget.destroy()

        if not daily:
            lbl_empty = tk.Label(self.daily_strip, text="Daily forecast data not available.", font=FONTS["meta"], bg=COLORS["card_bg"], fg=COLORS["text_dim"])
            lbl_empty.pack(pady=10)
            return

        is_metric = (self.current_unit == "metric")
        unit_str = "°C" if is_metric else "°F"

        for day in daily[:5]:
            d_card = tk.Frame(self.daily_strip, bg="#162032", highlightbackground="#233149", highlightthickness=1, padx=12, pady=6)
            d_card.pack(fill="x", pady=2)

            # Day & Date
            day_str = f"{day.get('day', '')}  {day.get('date', '')}"
            lbl_day = tk.Label(d_card, text=day_str, font=FONTS["meta"], bg="#162032", fg=COLORS["text_main"], width=14, anchor="w")
            lbl_day.pack(side="left")

            # Condition Icon
            icon_img = self.weather_service.get_weather_icon(day.get("icon_code", "01d"), size=(30, 30))
            if icon_img:
                tk_icon = ImageTk.PhotoImage(icon_img)
                self.image_references.append(tk_icon)
                lbl_icon = tk.Label(d_card, image=tk_icon, bg="#162032")
                lbl_icon.image = tk_icon
                lbl_icon.pack(side="left", padx=8)

            # Condition description
            lbl_cond = tk.Label(d_card, text=day.get("condition", "Clear"), font=FONTS["subtitle"], bg="#162032", fg=COLORS["text_muted"], width=18, anchor="w")
            lbl_cond.pack(side="left", padx=8)

            # Min & Max Temperature
            min_val = day.get("min_c" if is_metric else "min_f", 0.0)
            max_val = day.get("max_c" if is_metric else "max_f", 0.0)
            temp_range = f"Low: {round(min_val)}{unit_str}   •   High: {round(max_val)}{unit_str}"
            lbl_temp_range = tk.Label(d_card, text=temp_range, font=FONTS["card_val"], bg="#162032", fg=COLORS["text_main"], anchor="e")
            lbl_temp_range.pack(side="right", padx=10)

    # -----------------------------------------------------------------
    # Unit Toggle (°C / °F)
    # -----------------------------------------------------------------
    def toggle_unit(self):
        """Toggles between Celsius and Fahrenheit and recalculates in-place."""
        self.current_unit = "imperial" if self.current_unit == "metric" else "metric"
        self.config_data["unit"] = self.current_unit
        save_config(self.config_data)

        # Update button text
        active_label = "°F Active" if self.current_unit == "imperial" else "°C Active"
        self.btn_unit_toggle.set_text(active_label)

        # Instantly re-render with cached data without requiring new network request!
        if self.current_weather_data:
            self._render_current_weather(self.current_weather_data)
            self._render_hourly_forecast(self.current_weather_data.get("hourly", []))
            self._render_daily_forecast(self.current_weather_data.get("daily", []))

    def _update_api_status_badge(self):
        if self.weather_service.has_api_key():
            self.lbl_api_status.config(text="● OpenWeatherMap API", fg=COLORS["accent_green"])
        else:
            self.lbl_api_status.config(text="● Free Live Global API", fg=COLORS["accent_gold"])

    # -----------------------------------------------------------------
    # Settings & API Key Dialog
    # -----------------------------------------------------------------
    def open_settings_dialog(self):
        """Displays modal to view or set OpenWeatherMap API key."""
        dialog = tk.Toplevel(self)
        dialog.title("OpenWeatherMap API Key Settings")
        dialog.geometry("520x360")
        dialog.resizable(False, False)
        dialog.configure(bg=COLORS["header_bg"])
        dialog.transient(self)
        dialog.grab_set()

        lbl_title = tk.Label(
            dialog,
            text="⚙️ OpenWeatherMap API Configuration",
            font=FONTS["heading"],
            bg=COLORS["header_bg"],
            fg=COLORS["text_main"]
        )
        lbl_title.pack(anchor="w", padx=20, pady=(20, 8))

        lbl_desc = tk.Label(
            dialog,
            text="Enter your free OpenWeatherMap API key below to query OpenWeatherMap directly.\n"
                 "If left empty, the application uses the Free Live Global weather engine automatically.",
            font=FONTS["meta"],
            bg=COLORS["header_bg"],
            fg=COLORS["text_muted"],
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=20, pady=(0, 16))

        # Input Entry
        lbl_entry = tk.Label(dialog, text="API Key:", font=FONTS["meta"], bg=COLORS["header_bg"], fg=COLORS["text_main"])
        lbl_entry.pack(anchor="w", padx=20, pady=(0, 4))

        key_entry = tk.Entry(dialog, font=FONTS["input"], bg=COLORS["input_bg"], fg=COLORS["text_main"], insertbackground=COLORS["primary"])
        key_entry.pack(fill="x", padx=20, ipady=6)
        key_entry.insert(0, self.config_data.get("owm_api_key", ""))

        lbl_tip = tk.Label(
            dialog,
            text="Get a free key at: openweathermap.org (free tier: 60 calls/min)",
            font=FONTS["small"],
            bg=COLORS["header_bg"],
            fg=COLORS["primary"]
        )
        lbl_tip.pack(anchor="w", padx=20, pady=(6, 16))

        btn_row = tk.Frame(dialog, bg=COLORS["header_bg"])
        btn_row.pack(fill="x", padx=20, pady=10)

        def save_key():
            new_key = key_entry.get().strip()
            self.config_data["owm_api_key"] = new_key
            save_config(self.config_data)
            self.weather_service.set_api_key(new_key)
            self._update_api_status_badge()
            dialog.destroy()
            self.show_banner("API Key saved successfully! Refreshing weather...", is_error=False)
            current_city = self.city_entry.get().strip() or "London"
            self.fetch_weather_async(current_city)

        def clear_key():
            key_entry.delete(0, tk.END)
            self.config_data["owm_api_key"] = ""
            save_config(self.config_data)
            self.weather_service.set_api_key("")
            self._update_api_status_badge()
            dialog.destroy()
            self.show_banner("Using Free Live Global API mode.", is_error=False)
            current_city = self.city_entry.get().strip() or "London"
            self.fetch_weather_async(current_city)

        btn_save = ModernButton(
            btn_row,
            text="Save & Connect",
            command=save_key,
            bg_color=COLORS["primary"],
            hover_color=COLORS["primary_hover"],
            text_color="#0B132B",
            width=130,
            height=34,
            radius=6
        )
        btn_save.pack(side="left", padx=(0, 8))

        btn_clear = ModernButton(
            btn_row,
            text="Clear / Use Free",
            command=clear_key,
            bg_color="#334155",
            hover_color="#475569",
            text_color=COLORS["text_main"],
            width=130,
            height=34,
            radius=6
        )
        btn_clear.pack(side="left", padx=8)

        btn_cancel = ModernButton(
            btn_row,
            text="Cancel",
            command=dialog.destroy,
            bg_color="#1E293B",
            hover_color="#334155",
            text_color=COLORS["text_dim"],
            width=80,
            height=34,
            radius=6
        )
        btn_cancel.pack(side="right")


def run_gui():
    """Starts the GUI application."""
    app = WeatherAppGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()
