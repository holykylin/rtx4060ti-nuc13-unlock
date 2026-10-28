@echo off
chcp 65001 >nul
setlocal
set "PY=E:\Comfy-Desktop\ComfyUI-Installs\ComfyUI (1)\ComfyUI\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
"%PY%" "%~dp0check_unlock.py" %*
set "RC=%ERRORLEVEL%"
echo.
if /i "%~1"=="--nopause" exit /b %RC%
if /i "%~2"=="--nopause" exit /b %RC%
pause
exit /b %RC%
