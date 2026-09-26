"""
SkyPulse Weather App - Main Unified Entry Point
Supports both Advanced Graphical UI (GUI) and Beginner/Intermediate Terminal Interface (CLI).

Usage:
    python main.py                  # Launch Advanced Tier GUI (Default)
    python main.py --cli            # Launch Beginner Tier CLI Interactive Mode
    python main.py --city "London"  # Quick one-shot weather report in terminal
    python main.py --version        # Display version and developer details

Developer / Owner: Muhammad Junaid
"""

import sys
import argparse
from config import DEVELOPER_NAME, APP_NAME, APP_VERSION, REPO_URL

def main():
    parser = argparse.ArgumentParser(
        description=f"{APP_NAME} v{APP_VERSION} - Built by {DEVELOPER_NAME}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  python main.py                  Launch graphical desktop application
  python main.py --cli            Launch interactive command-line interface
  python main.py --city "Tokyo"   Fetch quick terminal forecast for Tokyo
  python main.py --locate         Detect current location and report weather

Developer: {DEVELOPER_NAME}
Repository: {REPO_URL}
"""
    )
    parser.add_argument("--cli", "-c", action="store_true", help="Launch in Interactive Command Line (CLI) mode")
    parser.add_argument("--city", "-q", type=str, help="Quick query for a specific city name or ZIP code")
    parser.add_argument("--locate", "-l", action="store_true", help="Auto-detect current location and print weather")
    parser.add_argument("--version", "-v", action="version", version=f"{APP_NAME} v{APP_VERSION} by {DEVELOPER_NAME}")

    args = parser.parse_args()

    # One-shot command line query
    if args.city or args.locate:
        from config import load_config
        from weather_service import WeatherService, WeatherAppError
        from weather_cli import format_weather_display, print_banner

        config = load_config()
        service = WeatherService(api_key=config.get("owm_api_key", ""))
        print_banner()

        target = args.city
        if args.locate:
            print("Detecting location via ipinfo.io...")
            loc = service.detect_user_location()
            target = loc.get("city", "London")
            print(f"Detected: {target}, {loc.get('country', '')}")

        try:
            data = service.fetch_weather(target)
            format_weather_display(data)
        except WeatherAppError as e:
            print(f"Error: {e}")
        return

    # Interactive CLI mode
    if args.cli:
        from weather_cli import run_cli
        run_cli()
        return

    # Default: Launch Advanced GUI mode
    try:
        from weather_gui import run_gui
        run_gui()
    except Exception as e:
        print(f"Could not initialize GUI: {e}")
        print("Falling back to Interactive CLI mode...")
        from weather_cli import run_cli
        run_cli()

if __name__ == "__main__":
    main()
