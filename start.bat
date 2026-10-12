@echo off
setlocal
title Starting PentAGI
cd /d "%~dp0"
if not exist ".env" (
    echo Create your private .env using .env.example and .env.opencode.example.
    echo See OPENCODE_SETUP.md before starting.
    exit /b 1
)
if not exist "frontend\dist\index.html" (
    echo Build the frontend first. See OPENCODE_SETUP.md.
    exit /b 1
)
if not exist "local-build\pentagi" (
    echo Build the Linux backend first. See OPENCODE_SETUP.md.
    exit /b 1
)
docker info >nul 2>&1
if errorlevel 1 (
    echo Start Docker Desktop and try again.
    exit /b 1
)
docker compose up -d --build
if errorlevel 1 exit /b 1
start "" "https://localhost:8443"
echo PentAGI is available at https://localhost:8443
endlocal
