@echo off
chcp 65001 >nul

echo ==========================================
echo   Task Management Server Startup
echo ==========================================

REM Check if Python is installed
echo Checking Python installation...

REM Try to find a working Python installation
set PYTHON_EXE=
if exist "C:\Users\ygu\AppData\Local\Programs\Python\Python313\python.exe" (
    set PYTHON_EXE=C:\Users\ygu\AppData\Local\Programs\Python\Python313\python.exe
    echo Using system Python: %PYTHON_EXE%
) else (
    REM Fallback to system PATH python
    python --version >nul 2>&1
    if not errorlevel 1 (
        set PYTHON_EXE=python
        echo Using system Python from PATH
    )
)

if "%PYTHON_EXE%"=="" (
    echo ❌ ERROR: Python not found, please install Python 3.7+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

%PYTHON_EXE% --version
if errorlevel 1 (
    echo ❌ ERROR: Python installation is corrupted
    pause
    exit /b 1
) else (
    echo ✓ Python is installed
)

REM Change to parent directory to maintain correct module paths
cd /d "%~dp0.."

REM Check dependencies
echo.
echo Checking dependencies...
%PYTHON_EXE% -c "import flask, socketio, requests" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON_EXE% -m pip install -r server\requirements.txt
    if errorlevel 1 (
        echo ❌ ERROR: Failed to install dependencies
        echo Please check your internet connection and try again
        pause
        exit /b 1
    )
) else (
    echo ✓ Dependencies installed
)

REM Test server module
echo.
echo Testing server module...
%PYTHON_EXE% -c "from server.app import create_app; print('✓ Server module OK')" 2>nul
if errorlevel 1 (
    echo ❌ ERROR: Server module cannot be imported
    echo Please ensure all project files are in place
    pause
    exit /b 1
)

echo.
echo ========================================
echo Starting Task Management Server...
echo Server will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo ========================================

%PYTHON_EXE% -m server.app

if errorlevel 1 (
    echo.
    echo ❌ ERROR: Server failed to start
    echo Common solutions:
    echo 1. Check if port 5000 is already in use
    echo 2. Run: netstat -ano ^| findstr :5000
    echo 3. Check firewall settings
    echo 4. Review error messages above
    pause
)

echo.
echo Server stopped.
pause
