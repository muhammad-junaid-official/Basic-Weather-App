@echo off
title SkyPulse Weather CLI - Muhammad Junaid
python main.py --cli
if errorlevel 1 (
    echo Python failed or was not found in system PATH.
    echo Trying local user installation...
    "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" main.py --cli
)
pause
