@echo off
title SalaryScope - Employee Salary Prediction System
cd /d "%~dp0"
where python >nul 2>nul
if %errorlevel%==0 (
    python app.py
) else (
    py app.py
)
if errorlevel 1 (
    echo.
    echo Could not start. Make sure Python 3.6 or newer is installed.
    pause
)
