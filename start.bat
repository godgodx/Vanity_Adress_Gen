@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM Vanity Address Generator - Windows startup script.

echo.
echo  ================================================================
echo   VANITY ADDRESS GENERATOR - OFFLINE ADDRESS GENERATION
echo  ================================================================
echo   Targets: Bitcoin, Ethereum, Tor v3 onion
echo  ================================================================
echo.

cd /d "%~dp0"

set "PYTHON_CMD="
set "CHECK_ONLY=0"

if /i "%~1"=="--check" (
    set "CHECK_ONLY=1"
)

echo [SYSTEM] Checking Python...
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !errorlevel! equ 0 (
    set "PYTHON_CMD=python"
) else (
    py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    echo ERROR: Python 3.10 or newer is required.
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('!PYTHON_CMD! --version 2^>^&1') do set "PYTHON_VERSION=%%i"
echo [OK] Python !PYTHON_VERSION! detected.

if not exist "main.py" (
    echo ERROR: main.py not found in the project directory.
    pause
    exit /b 1
)

if not exist "vanity_generators.py" (
    echo ERROR: vanity_generators.py not found in the project directory.
    pause
    exit /b 1
)

if not exist "vanity_core.py" (
    echo ERROR: vanity_core.py not found in the project directory.
    pause
    exit /b 1
)

echo [SYSTEM] Checking required dependencies...
!PYTHON_CMD! -c "import cryptography, Crypto.Hash.keccak, base58, tkinter" >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: Some required dependencies are missing.
    set /p INSTALL="Install required Python dependencies now? (y/N): "
    if /i "!INSTALL!"=="y" (
        echo [SYSTEM] Installing dependencies...
        !PYTHON_CMD! -m pip install --user -r requirements.txt
        !PYTHON_CMD! -c "import cryptography, Crypto.Hash.keccak, base58, tkinter" >nul 2>&1
        if !errorlevel! neq 0 (
            echo ERROR: Dependency installation failed.
            pause
            exit /b 1
        )
    ) else (
        echo Cannot continue without required dependencies.
        pause
        exit /b 1
    )
)

echo [OK] Required dependencies are available.

!PYTHON_CMD! -c "import coincurve" >nul 2>&1
if !errorlevel! neq 0 (
    echo [INFO] coincurve is not installed. The app will use a slower compatible fallback.
)

if not exist "output" (
    mkdir output
    echo [OK] Created output directory.
)

if "!CHECK_ONLY!"=="1" (
    echo [OK] Startup checks passed.
    exit /b 0
)

echo.
echo  SECURITY WARNING
echo  ---------------------------------------------------------------
echo   This application generates real private keys.
echo   Anyone with a generated private key can control its funds.
echo   Keep output files private, encrypted, and offline when possible.
echo  ---------------------------------------------------------------
set /p AGREE="Continue? (y/N): "
if /i not "!AGREE!"=="y" (
    if /i not "!AGREE!"=="yes" (
        echo Aborted.
        pause
        exit /b 1
    )
)

echo.
echo [START] Launching application...
!PYTHON_CMD! main.py

if !errorlevel! neq 0 (
    echo.
    echo ERROR: Application exited with an error.
    pause
    exit /b 1
)

echo.
echo Application closed successfully.
pause
