@echo off
REM Vanity Address Generator - Windows Startup Script
REM Secure offline cryptocurrency address generator

setlocal EnableDelayedExpansion

REM ASCII Banner (Windows compatible)
echo.
echo  ====================================================================
echo  ^|  VANITY ADDRESS GENERATOR - OFFLINE CRYPTO ADDRESS GENERATOR  ^|
echo  ====================================================================
echo  ^|                                                                ^|
echo  ^|  [*] Bitcoin    [*] Ethereum    [*] Tor (.onion)              ^|
echo  ^|  [*] Secure     [*] Offline     [*] Multithreaded             ^|
echo  ^|                                                                ^|
echo  ====================================================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo [SYSTEM CHECK] Verifying environment...

REM Check if Python is installed
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo ERROR: Python not found. Please install Python 3.7 or newer.
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)

REM Check Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Found Python %PYTHON_VERSION%

REM Check if main.py exists
if not exist "main.py" (
    echo ERROR: main.py not found in current directory.
    pause
    exit /b 1
)

REM Check dependencies
echo [INFO] Checking dependencies...
python -c "import cryptography, Crypto.Hash.keccak, base58, tkinter" >nul 2>&1
if !errorlevel! neq 0 (
    echo WARNING: Some dependencies are missing.
    echo.
    set /p INSTALL="Install missing dependencies? (y/N): "
    if /i "!INSTALL!"=="y" (
        echo [INFO] Installing dependencies...
        if exist "requirements.txt" (
            pip install -r requirements.txt --user
        ) else (
            pip install cryptography^>=41.0.0 pycryptodome^>=3.19.0 base58^>=2.1.1 --user
        )
        
        REM Check again
        python -c "import cryptography, Crypto.Hash.keccak, base58, tkinter" >nul 2>&1
        if !errorlevel! neq 0 (
            echo ERROR: Failed to install dependencies.
            pause
            exit /b 1
        )
    ) else (
        echo Cannot proceed without dependencies.
        pause
        exit /b 1
    )
)

echo [SUCCESS] All dependencies satisfied.

REM Create output directory if it doesn't exist
if not exist "output" (
    mkdir output
    echo [INFO] Created output directory.
)

REM Security warnings
echo.
echo  =====================================================
echo  ^|              SECURITY WARNINGS                  ^|
echo  =====================================================
echo  ^| * This generates REAL private keys with access ^|
echo  ^|   to funds                                      ^|
echo  ^| * Keep private keys secure and never share them^|
echo  ^| * Use on offline/air-gapped systems for        ^|
echo  ^|   maximum security                              ^|
echo  ^| * Test with small amounts before using for     ^|
echo  ^|   large funds                                   ^|
echo  ^| * You are responsible for key security and     ^|
echo  ^|   fund safety                                   ^|
echo  =====================================================
echo.
set /p AGREE="I understand the security implications (y/N): "
if /i not "!AGREE!"=="y" (
    echo Aborted by user.
    pause
    exit /b 1
)

REM Launch application
echo.
echo [STARTING] Launching Vanity Address Generator...
echo [INFO] Close the window or press Ctrl+C to stop
echo.

python main.py

if !errorlevel! neq 0 (
    echo.
    echo ERROR: Application crashed or exited with error.
    pause
    exit /b 1
)

echo.
echo Application closed successfully.
pause
