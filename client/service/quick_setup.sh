#!/bin/bash
# Quick setup script for Task Client
# This script demonstrates the new modular architecture

echo "======================================"
echo "Task Client Quick Setup"
echo "======================================"
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
SERVER_URL="http://localhost:5000"
CLIENT_NAME=$(hostname)
INSTALL_DIR="$HOME/.task_client"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --server-url)
            SERVER_URL="$2"
            shift 2
            ;;
        --client-name)
            CLIENT_NAME="$2"
            shift 2
            ;;
        --install-dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --server-url URL    Server URL (default: http://localhost:5000)"
            echo "  --client-name NAME  Client name (default: hostname)"
            echo "  --install-dir DIR   Installation directory (default: ~/.task_client)"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --server-url http://192.168.1.100:5000 --client-name worker-01"
            echo "  $0 --client-name gpu-server"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Configuration:"
echo "  Server URL: $SERVER_URL"
echo "  Client Name: $CLIENT_NAME"
echo "  Install Directory: $INSTALL_DIR"
echo

# Check if already installed
if [ -f "$INSTALL_DIR/config.json" ]; then
    echo "⚠️  Client appears to be already installed in $INSTALL_DIR"
    echo "Do you want to:"
    echo "1. Update existing installation"
    echo "2. Reinstall (remove existing)"
    echo "3. Cancel"
    read -p "Choose option (1-3): " choice
    
    case $choice in
        1)
            echo "🔄 Updating existing installation..."
            python3 "$SCRIPT_DIR/client_installer.py" update
            if [ $? -eq 0 ]; then
                echo "✅ Update completed successfully!"
                echo "Restart the client to apply changes."
            else
                echo "❌ Update failed"
                exit 1
            fi
            exit 0
            ;;
        2)
            echo "🗑️  Removing existing installation..."
            python3 "$SCRIPT_DIR/client_installer.py" uninstall --remove-data
            ;;
        3)
            echo "Cancelled"
            exit 0
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac
fi

# Install client
echo "🔧 Installing Task Client..."
python3 "$SCRIPT_DIR/client_installer.py" install \
    --server-url "$SERVER_URL" \
    --client-name "$CLIENT_NAME" \
    --install-dir "$INSTALL_DIR"

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Installation completed successfully!"
    echo ""
    echo "📋 What's installed:"
    echo "  📁 Installation directory: $INSTALL_DIR"
    echo "  ⚙️  Configuration file: $INSTALL_DIR/config.json"
    echo "  📝 Log directory: $INSTALL_DIR/logs"
    echo "  💼 Work directory: $INSTALL_DIR/work"
    echo ""
    echo "🚀 To start the client:"
    echo "  $INSTALL_DIR/start_client.sh"
    echo ""
    echo "🛑 To stop the client:"
    echo "  $INSTALL_DIR/stop_client.sh"
    echo ""
    echo "📊 To check status:"
    echo "  python3 $SCRIPT_DIR/client_installer.py status"
    echo ""
    echo "🔄 To update core files (without reinstalling):"
    echo "  python3 $SCRIPT_DIR/client_installer.py update"
    echo ""
    echo "🗑️  To uninstall:"
    echo "  python3 $SCRIPT_DIR/client_installer.py uninstall"
    echo ""
    
    # Ask if user wants to start immediately
    read -p "Would you like to start the client now? (y/N): " start_now
    if [[ $start_now =~ ^[Yy]$ ]]; then
        echo "🚀 Starting client..."
        "$INSTALL_DIR/start_client.sh"
    else
        echo "👍 You can start the client later using: $INSTALL_DIR/start_client.sh"
    fi
else
    echo "❌ Installation failed"
    exit 1
fi
