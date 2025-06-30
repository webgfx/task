@echo off
REM Quick setup script for Task Client on Windows
REM This script demonstrates the new modular architecture

echo ======================================
echo Task Client Quick Setup
echo ======================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"

REM Default values
set "SERVER_URL=http://localhost:5000"
for /f "tokens=*" %%i in ('hostname') do set "MACHINE_NAME=%%i"
set "INSTALL_DIR=%USERPROFILE%\.task_client"

REM Parse command line arguments
:parse_args
if "%~1"=="" goto :done_parsing
if "%~1"=="--server-url" (
    set "SERVER_URL=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--machine-name" (
    set "MACHINE_NAME=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--install-dir" (
    set "INSTALL_DIR=%~2"
    shift
    shift
    goto :parse_args
)
if "%~1"=="--help" (
    echo Usage: %0 [OPTIONS]
    echo.
    echo Options:
    echo   --server-url URL    Server URL ^(default: http://localhost:5000^)
    echo   --machine-name NAME Machine name ^(default: hostname^)
    echo   --install-dir DIR   Installation directory ^(default: %%USERPROFILE%%\.task_client^)
    echo   --help              Show this help message
    echo.
    echo Examples:
    echo   %0 --server-url http://192.168.1.100:5000 --machine-name worker-01
    echo   %0 --machine-name gpu-server
    exit /b 0
)
echo Unknown option: %~1
echo Use --help for usage information
exit /b 1

:done_parsing

echo Configuration:
echo   Server URL: %SERVER_URL%
echo   Machine Name: %MACHINE_NAME%
echo   Install Directory: %INSTALL_DIR%
echo.

REM Check if already installed
if exist "%INSTALL_DIR%\config.json" (
    echo ⚠️  Client appears to be already installed in %INSTALL_DIR%
    echo Do you want to:
    echo 1. Update existing installation
    echo 2. Reinstall ^(remove existing^)
    echo 3. Cancel
    set /p "choice=Choose option (1-3): "
    
    if "!choice!"=="1" (
        echo 🔄 Updating existing installation...
        python "%SCRIPT_DIR%client_installer.py" update
        if !errorlevel! equ 0 (
            echo ✅ Update completed successfully!
            echo Restart the client to apply changes.
        ) else (
            echo ❌ Update failed
            exit /b 1
        )
        exit /b 0
    )
    if "!choice!"=="2" (
        echo 🗑️  Removing existing installation...
        python "%SCRIPT_DIR%client_installer.py" uninstall --remove-data
    )
    if "!choice!"=="3" (
        echo Cancelled
        exit /b 0
    )
    if not "!choice!"=="1" if not "!choice!"=="2" if not "!choice!"=="3" (
        echo Invalid choice
        exit /b 1
    )
)

REM Install client
echo 🔧 Installing Task Client...
python "%SCRIPT_DIR%client_installer.py" install --server-url "%SERVER_URL%" --machine-name "%MACHINE_NAME%" --install-dir "%INSTALL_DIR%"

if %errorlevel% equ 0 (
    echo.
    echo ✅ Installation completed successfully!
    echo.
    echo 📋 What's installed:
    echo   📁 Installation directory: %INSTALL_DIR%
    echo   ⚙️  Configuration file: %INSTALL_DIR%\config.json
    echo   📝 Log directory: %INSTALL_DIR%\logs
    echo   💼 Work directory: %INSTALL_DIR%\work
    echo.
    echo 🚀 To start the client:
    echo   %INSTALL_DIR%\start_client.bat
    echo.
    echo 🛑 To stop the client:
    echo   %INSTALL_DIR%\stop_client.bat
    echo.
    echo 📊 To check status:
    echo   python "%SCRIPT_DIR%client_installer.py" status
    echo.
    echo 🔄 To update core files ^(without reinstalling^):
    echo   python "%SCRIPT_DIR%client_installer.py" update
    echo.
    echo 🗑️  To uninstall:
    echo   python "%SCRIPT_DIR%client_installer.py" uninstall
    echo.
    
    REM Ask if user wants to start immediately
    set /p "start_now=Would you like to start the client now? (y/N): "
    if /i "!start_now!"=="y" (
        echo 🚀 Starting client...
        "%INSTALL_DIR%\start_client.bat"
    ) else (
        echo 👍 You can start the client later using: %INSTALL_DIR%\start_client.bat
    )
) else (
    echo ❌ Installation failed
    exit /b 1
)

pause
