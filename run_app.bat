@echo off
title SkyPulse Weather App - Muhammad Junaid
python main.py
if errorlevel 1 (
    echo Python failed or was not found in system PATH.
    echo Trying local user installation...
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py
)
pause
