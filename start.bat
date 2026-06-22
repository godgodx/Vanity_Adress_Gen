@echo off
setlocal EnableDelayedExpansion

REM Vanity Address Generator - Windows startup script.

echo.
echo  ================================================================
echo   VANITY ADDRESS GENERATOR - OFFLINE ADDRESS GENERATION
echo  ================================================================
echo   Targets: Bitcoin, Ethereum, Tor v3 onion
echo  ================================================================
echo.

cd /d "%~dp0"

echo [SYSTEM] Checking Python...
python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: Python 3.10 or newer is required.
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo [OK] Python %PYTHON_VERSION% detected.

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

echo [SYSTEM] Checking dependencies...
python -c "import cryptography, Crypto.Hash.keccak, base58, coincurve, tkinter" >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: Some dependencies are missing.
    set /p INSTALL="Install missing Python dependencies? (y/N): "
    if /i "!INSTALL!"=="y" (
        echo [SYSTEM] Installing dependencies...
        python -m pip install --user -r requirements.txt
        python -c "import cryptography, Crypto.Hash.keccak, base58, coincurve, tkinter" >nul 2>&1
        if !errorlevel! neq 0 (
            echo ERROR: Dependency installation failed.
            pause
            exit /b 1
        )
    ) else (
        echo Cannot continue without dependencies.
        pause
        exit /b 1
    )
)

echo [OK] Dependencies are available.

if not exist "output" (
    mkdir output
    echo [OK] Created output directory.
)

echo.
echo  SECURITY WARNING
echo  ---------------------------------------------------------------
echo   This application generates real private keys.
echo   Anyone with a generated private key can control its funds.
echo   Keep output files private, encrypted, and offline when possible.
echo  ---------------------------------------------------------------
set /p AGREE="Type YES to continue: "
if not "!AGREE!"=="YES" (
    echo Aborted.
    pause
    exit /b 1
)

echo.
echo [START] Launching application...
python main.py

if !errorlevel! neq 0 (
    echo.
    echo ERROR: Application exited with an error.
    pause
    exit /b 1
)

echo.
echo Application closed successfully.
pause
