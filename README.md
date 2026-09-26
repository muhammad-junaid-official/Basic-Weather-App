# 🌤️ SkyPulse Weather App (Basic Weather App — Task 4)

[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![GUI](https://img.shields.io/badge/GUI-Tkinter%20%2B%20Pillow-blueviolet.svg)](https://docs.python.org/3/library/tkinter.html)
[![API](https://img.shields.io/badge/API-OpenWeatherMap%20API-orange.svg)](https://openweathermap.org/)
[![Developer](https://img.shields.io/badge/Developer-Muhammad%20Junaid-brightgreen.svg)](https://github.com/muhammad-junaid-official)

A real-time weather application developed in Python. It includes both an **Interactive Command-Line Interface (Beginner Tier)** and an **Advanced Graphical User Interface (Advanced Tier)** featuring live hourly and 5-day forecasts, condition icons, instant unit switching (°C / °F), automatic location detection, and in-app error handling.

> **Developer & Project Owner:** [Muhammad Junaid](https://github.com/muhammad-junaid-official)  
> **Repository:** [https://github.com/muhammad-junaid-official/Basic-Weather-App.git](https://github.com/muhammad-junaid-official/Basic-Weather-App.git)

---

## 📋 Feature Checklist

### ✅ Beginner Tier (CLI)
- [x] **Location Query**: Prompt user to enter any city name or ZIP code (supports international and US zip codes).
- [x] **API Integration**: Make HTTP API calls to OpenWeatherMap (and live global engine fallback) and parse JSON responses.
- [x] **Comprehensive Weather Metrics**:
  - Current temperature in both **°C** and **°F**
  - "Feels like" temperature
  - Humidity percentage (%)
  - Weather condition description (e.g., "Partly Cloudy", "Heavy Rain")
  - Wind speed in m/s, km/h, and mph with compass direction (e.g. NNW, SE)
  - Atmospheric pressure (hPa) & visibility (km)
  - Sunrise and sunset times
- [x] **Graceful Error Handling**:
  - City not found (404) with typo suggestions
  - Invalid API key (401) with setup guidance
  - Rate limit protection (429)
  - Network timeouts and connectivity failures
- [x] **Input Validation**: Reject empty inputs and whitespace gracefully.

### 🌟 Advanced Tier (GUI)
- [x] **Modern Desktop GUI**: Built with Tkinter and Pillow featuring a dark glassmorphic palette, high-DPI scaling, and responsive cards.
- [x] **Dynamic Weather Icons**: Displays high-resolution weather condition icons streamed from OpenWeatherMap CDN with local disk caching and PIL fallback graphics.
- [x] **Hourly Forecast Panel**: Shows forecast for the next 6 to 12 hours with hour timestamps, condition icons, temperatures, and rain probability (`💧 %`).
- [x] **Daily Forecast Panel**: Displays the next 5 days with day names, dates, weather condition icons, and Min/Max temperature ranges.
- [x] **Unit Toggle Switch**: Instant one-click switch between **Celsius (°C)** and **Fahrenheit (°F)** with instantaneous in-place recalculation (no redundant API calls).
- [x] **Automatic Location Detection**: Detects user location automatically on launch or via the **"📍 Locate Me"** button using IP geolocation (`ipinfo.io`).
- [x] **In-App Notification Banners**: Clean status, info, and error notifications displayed directly inside the GUI rather than terminal print statements or intrusive popup dialogs.
- [x] **Background Threading**: All network operations run asynchronously in worker threads so the GUI never freezes or becomes unresponsive.
- [x] **API Key Settings Modal**: Interactive in-app dialog allowing users to enter, test, and save their OpenWeatherMap API key with persistent storage in `config.json`.
- [x] **Out-of-the-Box Operation**: If no API key is provided yet, seamlessly connects to the Open-Meteo live global engine so new users can run and test the app immediately.

---

## 🏗️ Project Architecture

```
weather app/
│
├── main.py                  # Main entry point (launches GUI by default or CLI via --cli)
├── weather_gui.py           # Advanced Tier graphical desktop application
├── weather_cli.py           # Beginner Tier interactive terminal application
├── weather_service.py       # Weather engine, OpenWeatherMap API, geocoding & caching
├── config.py                # Configuration manager and developer constants
│
├── assets/
│   ├── cache/               # Downloaded weather icon cache
│   └── icons/               # Local graphical resources
│
├── run_app.bat              # One-click Windows desktop launcher (GUI)
├── run_cli.bat              # One-click Windows terminal launcher (CLI)
├── requirements.txt         # Project dependencies (requests, pillow)
├── .gitignore               # Ignored cache, bytecode, and local config files
└── README.md                # Project documentation and specifications
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.10, 3.11, or 3.12 installed.

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/muhammad-junaid-official/Basic-Weather-App.git
cd "Basic-Weather-App"
```

Install dependencies:
```bash
pip install -r requirements.txt
```

---

## 🎮 Running the Application

### Option A: Launch the Graphical App (Advanced Tier)
```bash
python main.py
```
*Or double-click `run_app.bat` on Windows.*

### Option B: Launch the Interactive CLI (Beginner Tier)
```bash
python main.py --cli
```
*Or double-click `run_cli.bat` on Windows.*

### Option C: Quick One-Shot Terminal Query
```bash
python main.py --city "Tokyo"
python main.py --city "London, UK"
python main.py --city "90210"
python main.py --locate
```

---

## 🔑 OpenWeatherMap API Setup

1. Sign up for a free account at [OpenWeatherMap](https://openweathermap.org/).
2. Navigate to your **API Keys** tab and copy your key.
3. Add the key in any of the following ways:
   - **Through GUI**: Click the **"⚙️ API Key"** button on the top right, paste your key, and click **"Save & Connect"**.
   - **Through CLI**: Type `key` at the prompt and enter your API key.
   - **Through Environment Variable**:
     ```bash
     set OPENWEATHERMAP_API_KEY=your_api_key_here
     ```

*Note: Newly created OpenWeatherMap keys typically take 10 to 60 minutes to activate on OpenWeatherMap's servers. During this period, the application will notify you and seamlessly allow using the Free Live Global engine.*

---

## 🛠️ Technologies Used

| Technology | Purpose |
|------------|---------|
| **Python 3** | Core programming language |
| **Tkinter & ttk** | Graphical user interface framework with DPI awareness |
| **Pillow (PIL)** | Image rendering, resizing, and dynamic icon generation |
| **Requests** | HTTP client for RESTful weather API consumption |
| **Threading** | Asynchronous non-blocking network calls |
| **OpenWeatherMap API** | Official free weather API for current & 5-day forecasts |
| **ipinfo.io API** | IP-based automatic user location detection |

---

## 👤 Author & Developer

**Muhammad Junaid**  
- GitHub: [@muhammad-junaid-official](https://github.com/muhammad-junaid-official)  
- Repository: [Basic-Weather-App](https://github.com/muhammad-junaid-official/Basic-Weather-App.git)

---

## 📄 License
This project is open-source under the MIT License.
