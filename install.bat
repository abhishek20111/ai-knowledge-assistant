@echo off
title Install Dependencies (venv)
color 0A
echo.
echo  Installing Python packages into venv...
echo.

set ROOT=%~dp0
set VENV=%ROOT%venv
set BACKEND=%ROOT%backend

if not exist "%VENV%\Scripts\activate.bat" (
    echo  Creating venv first...
    python -m venv "%VENV%"
)

"%VENV%\Scripts\pip.exe" install --upgrade pip
"%VENV%\Scripts\pip.exe" install -r "%BACKEND%\requirements.txt"

if %errorlevel% equ 0 (
    echo.
    echo  ✓ All dependencies installed in venv successfully!
    echo.
    echo  To activate venv manually:
    echo    %VENV%\Scripts\activate.bat
) else (
    echo.
    echo  ✗ Install failed. Check the errors above.
)
echo.
pause
