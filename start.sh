#!/bin/bash

# Vanity Address Generator - Linux Startup Script
# Secure offline cryptocurrency address generator

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color

# ASCII Banner
echo -e "${GREEN}"
echo "  ╦  ╦┌─┐┌┐┌┬┌┬┐┬ ┬  ╔═╗┌┬┐┌┬┐┬─┐┌─┐┌─┐┌─┐  ╔═╗┌─┐┌┐┌┌─┐┬─┐┌─┐┌┬┐┌─┐┬─┐"
echo "  ╚╗╔╝├─┤││││ │ └┬┘  ╠═╣ ││ ││├┬┘├┤ └─┐└─┐  ║ ╦├┤ │││├┤ ├┬┘├─┤ │ │ │├┬┘"
echo "   ╚╝ ┴ ┴┘└┘┴ ┴  ┴   ╩ ╩─┴┘─┴┘┴└─└─┘└─┘└─┘  ╚═╝└─┘┘└┘└─┘┴└─┴ ┴ ┴ └─┘┴└─"
echo "                                                                           "
echo -e "${CYAN}>> OFFLINE CRYPTO ADDRESS GENERATOR <<${NC}"
echo ""

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python version
check_python_version() {
    if command_exists python3; then
        local version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
        local major=$(echo $version | cut -d. -f1)
        local minor=$(echo $version | cut -d. -f2)
        
        if [ "$major" -ge 3 ] && [ "$minor" -ge 7 ]; then
            echo -e "${GREEN}✓ Python $version detected${NC}"
            return 0
        else
            echo -e "${RED}✗ Python 3.7+ required, found $version${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ Python 3 not found${NC}"
        return 1
    fi
}

# Function to check dependencies
check_dependencies() {
    echo -e "${BLUE}[INFO]${NC} Checking dependencies..."
    
    # Check if requirements are installed
    local missing_deps=()
    
    if ! python3 -c "import cryptography" 2>/dev/null; then
        missing_deps+=("cryptography")
    fi
    
    if ! python3 -c "import Crypto.Hash.keccak" 2>/dev/null; then
        missing_deps+=("pycryptodome")
    fi
    
    if ! python3 -c "import base58" 2>/dev/null; then
        missing_deps+=("base58")
    fi
    
    if ! python3 -c "import tkinter" 2>/dev/null; then
        missing_deps+=("tkinter")
    fi
    
    if [ ${#missing_deps[@]} -eq 0 ]; then
        echo -e "${GREEN}✓ All dependencies satisfied${NC}"
        return 0
    else
        echo -e "${YELLOW}⚠ Missing dependencies: ${missing_deps[*]}${NC}"
        return 1
    fi
}

# Function to install dependencies
install_dependencies() {
    echo -e "${BLUE}[INFO]${NC} Installing dependencies..."
    
    # Check if pip is available
    if ! command_exists pip3; then
        echo -e "${RED}✗ pip3 not found. Please install pip first.${NC}"
        exit 1
    fi
    
    # Install from requirements.txt if it exists
    if [ -f "requirements.txt" ]; then
        echo -e "${BLUE}[INFO]${NC} Installing from requirements.txt..."
        pip3 install -r requirements.txt --user
    else
        echo -e "${BLUE}[INFO]${NC} Installing core dependencies manually..."
        pip3 install cryptography>=41.0.0 pycryptodome>=3.19.0 base58>=2.1.1 --user
    fi
    
    # Check for tkinter (often needs separate installation on Linux)
    if ! python3 -c "import tkinter" 2>/dev/null; then
        echo -e "${YELLOW}⚠ tkinter not available${NC}"
        echo -e "${BLUE}[INFO]${NC} Install tkinter with your package manager:"
        echo "  Ubuntu/Debian: sudo apt-get install python3-tk"
        echo "  RHEL/CentOS:   sudo yum install tkinter"
        echo "  Arch Linux:    sudo pacman -S tk"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# Function to check file permissions
check_permissions() {
    if [ ! -f "main.py" ]; then
        echo -e "${RED}✗ main.py not found in current directory${NC}"
        exit 1
    fi
    
    if [ ! -r "main.py" ]; then
        echo -e "${RED}✗ Cannot read main.py${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ Application files accessible${NC}"
}

# Function to create output directory
setup_environment() {
    if [ ! -d "output" ]; then
        mkdir -p output
        echo -e "${GREEN}✓ Created output directory${NC}"
    fi
    
    # Set secure permissions for output directory
    chmod 750 output 2>/dev/null
}

# Function to display security warnings
show_security_warnings() {
    echo -e "${YELLOW}"
    echo "⚠️  SECURITY WARNINGS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "• This generates REAL private keys with access to funds"
    echo "• Keep private keys secure and never share them"
    echo "• Use on offline/air-gapped systems for maximum security"
    echo "• Test with small amounts before using for large funds"
    echo "• You are responsible for key security and fund safety"
    echo -e "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    
    read -p "I understand the security implications (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborted by user${NC}"
        exit 1
    fi
}

# Function to run the application
run_application() {
    echo -e "${GREEN}[STARTING]${NC} Launching Vanity Address Generator..."
    echo -e "${BLUE}[INFO]${NC} Press Ctrl+C to stop"
    echo ""
    
    # Run with proper error handling
    if ! python3 main.py; then
        echo -e "${RED}✗ Application crashed or exited with error${NC}"
        exit 1
    fi
}

# Main execution flow
main() {
    # Change to script directory
    cd "$(dirname "$0")"
    
    echo -e "${BLUE}[SYSTEM CHECK]${NC} Verifying environment..."
    
    # System checks
    if ! check_python_version; then
        echo -e "${RED}Please install Python 3.7 or newer${NC}"
        exit 1
    fi
    
    check_permissions
    
    # Dependency checks
    if ! check_dependencies; then
        echo ""
        read -p "Install missing dependencies? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            install_dependencies
            echo ""
            if ! check_dependencies; then
                echo -e "${RED}✗ Failed to install dependencies${NC}"
                exit 1
            fi
        else
            echo -e "${RED}Cannot proceed without dependencies${NC}"
            exit 1
        fi
    fi
    
    setup_environment
    show_security_warnings
    run_application
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}[INTERRUPTED]${NC} Application stopped by user"; exit 130' INT

# Run main function
main "$@"
