#!/usr/bin/env bash

# Vanity Address Generator - Linux/macOS startup script.

set -u

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

PYTHON_BIN="${PYTHON_BIN:-python3}"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

check_python_version() {
    if ! command_exists "$PYTHON_BIN"; then
        echo -e "${RED}ERROR: $PYTHON_BIN not found. Install Python 3.10 or newer.${NC}"
        return 1
    fi

    if "$PYTHON_BIN" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
        local version
        version=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
        echo -e "${GREEN}OK: Python $version detected.${NC}"
        return 0
    fi

    local version
    version=$("$PYTHON_BIN" -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
    echo -e "${RED}ERROR: Python 3.10 or newer is required. Found $version.${NC}"
    return 1
}

check_dependencies() {
    echo -e "${BLUE}INFO: Checking dependencies...${NC}"
    local missing_deps=()

    "$PYTHON_BIN" -c "import cryptography" 2>/dev/null || missing_deps+=("cryptography")
    "$PYTHON_BIN" -c "import Crypto.Hash.keccak" 2>/dev/null || missing_deps+=("pycryptodome")
    "$PYTHON_BIN" -c "import base58" 2>/dev/null || missing_deps+=("base58")
    "$PYTHON_BIN" -c "import tkinter" 2>/dev/null || missing_deps+=("tkinter")

    if [ ${#missing_deps[@]} -eq 0 ]; then
        echo -e "${GREEN}OK: All dependencies are available.${NC}"
        return 0
    fi

    echo -e "${YELLOW}WARNING: Missing dependencies: ${missing_deps[*]}${NC}"
    return 1
}

install_dependencies() {
    echo -e "${BLUE}INFO: Installing Python dependencies...${NC}"

    if "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
        "$PYTHON_BIN" -m pip install --user -r requirements.txt
    elif command_exists pip3; then
        pip3 install --user -r requirements.txt
    else
        echo -e "${RED}ERROR: pip is not available. Install pip and rerun this script.${NC}"
        exit 1
    fi

    if ! "$PYTHON_BIN" -c "import tkinter" 2>/dev/null; then
        echo -e "${YELLOW}WARNING: tkinter is not available.${NC}"
        echo "Install tkinter with your package manager if the GUI does not open:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-tk"
        echo "  RHEL/CentOS:   sudo yum install tkinter"
        echo "  Arch Linux:    sudo pacman -S tk"
    fi
}

check_files() {
    if [ ! -f "main.py" ] || [ ! -f "vanity_generators.py" ] || [ ! -f "vanity_core.py" ]; then
        echo -e "${RED}ERROR: Application files are missing. Run this script from the project directory.${NC}"
        exit 1
    fi
    echo -e "${GREEN}OK: Application files found.${NC}"
}

setup_environment() {
    mkdir -p output
    chmod 750 output 2>/dev/null || true
}

show_security_warning() {
    echo
    echo "SECURITY WARNING"
    echo "------------------------------------------------------------"
    echo "This application generates real private keys."
    echo "Anyone with a generated private key can control its funds."
    echo "Keep output files private, encrypted, and offline when possible."
    echo "------------------------------------------------------------"
    read -r -p "Type YES to continue: " answer
    if [ "$answer" != "YES" ]; then
        echo "Aborted."
        exit 1
    fi
}

main() {
    cd "$(dirname "$0")"
    echo "Vanity Address Generator"
    echo "Offline Bitcoin, Ethereum, and Tor address generation"
    echo

    check_python_version || exit 1
    check_files

    if ! check_dependencies; then
        read -r -p "Install missing Python dependencies? (y/N): " answer
        if [[ "$answer" =~ ^[Yy]$ ]]; then
            install_dependencies
            check_dependencies || exit 1
        else
            echo "Cannot continue without dependencies."
            exit 1
        fi
    fi

    setup_environment
    if ! "$PYTHON_BIN" -c "import coincurve" 2>/dev/null; then
        echo -e "${YELLOW}INFO: coincurve is not installed. The app will use a slower compatible fallback.${NC}"
    fi
    show_security_warning

    echo -e "${GREEN}START: Launching application...${NC}"
    "$PYTHON_BIN" main.py
}

trap 'echo; echo "Interrupted."; exit 130' INT
main "$@"
