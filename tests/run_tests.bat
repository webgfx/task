@echo off
REM Official Test Runner for Distributed Task Management System
REM This batch file makes it easy to run official test scenarios

echo ================================================
echo  DISTRIBUTED TASK MANAGEMENT SYSTEM - TESTS
echo ================================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.13 and try again
    pause
    exit /b 1
)

REM Change to project directory
cd /d "%~dp0.."

echo Current directory: %CD%
echo.

REM Check if server is running by testing the port
echo Checking if server is running on port 5000...
netstat -an | find "5000" | find "LISTENING" >nul
if errorlevel 1 (
    echo WARNING: Server does not appear to be running on port 5000
    echo Please start the server with: python server/app.py
    echo.
    set /p continue="Continue anyway? (y/N): "
    if /i not "%continue%"=="y" exit /b 1
)

echo Server appears to be running
echo.

REM Run the test
if "%1"=="" (
    echo Running all official test scenarios...
    python tests/run_official_tests.py
) else (
    echo Running test scenario: %1
    python tests/run_official_tests.py %1
)

echo.
echo Test execution completed.
echo Check the output above for results.
echo.
pause
