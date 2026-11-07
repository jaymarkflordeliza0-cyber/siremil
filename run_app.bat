@echo off
title SalaryScope - Employee Salary Prediction System
cd /d "%~dp0"
python app.py
if errorlevel 1 pause
