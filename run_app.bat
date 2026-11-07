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
    echo Could not start. Make sure Python is installed (2.7 or any 3.x).
    pause
)
