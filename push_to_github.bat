@echo off
title Push Weather App to GitHub - Muhammad Junaid
echo ========================================================
echo   Pushing to GitHub: muhammad-junaid-official/Basic-Weather-App
echo ========================================================
echo.

set "GIT_CMD=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"

if exist "%GIT_CMD%" (
    "%GIT_CMD%" push origin main
) else (
    git push origin main
)

echo.
pause
