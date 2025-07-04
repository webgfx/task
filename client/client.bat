@echo off
chcp 65001 >nul

echo ==========================================
echo   Task Management Client Service Manager
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
    echo ERROR: Python not found, please install Python 3.7+
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

%PYTHON_EXE% --version
if errorlevel 1 (
    echo ERROR: Python installation is corrupted
    pause
    exit /b 1
) else (
    echo Python is installed
)

REM Check dependencies
echo.
echo Checking dependencies...
%PYTHON_EXE% -c "import flask, socketio, requests" >nul 2>&1
if errorlevel 1 (
    echo Installing dependencies...
    %PYTHON_EXE% -m pip install -r client\requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        echo Please check your internet connection and try again
        pause
        exit /b 1
    )
) else (
    echo Dependencies installed
)

REM Test client module
echo.
echo Testing client module...
cd ..
%PYTHON_EXE% -c "from client.client_runner import TaskClientRunner; print('✓ Client module OK')" 2>nul
if errorlevel 1 (
    echo ERROR: Client module cannot be imported
    echo Please ensure all project files are in place
    cd client
    pause
    exit /b 1
)
cd client

REM Test Windows service modules
echo.
echo Testing Windows service modules...
%PYTHON_EXE% -c "import win32serviceutil, win32service, win32event, servicemanager; print('✓ Windows service modules OK')" 2>nul
if errorlevel 1 (
    echo ERROR: Windows service modules missing
    echo Installing pywin32...
    %PYTHON_EXE% -m pip install pywin32
    if errorlevel 1 (
        echo ERROR: Failed to install pywin32
        echo Please install pywin32 manually: pip install pywin32
        pause
        exit /b 1
    ) else (
        echo pywin32 installed successfully
        echo Configuring pywin32...
        %PYTHON_EXE% -m pywin32_postinstall -install
        if errorlevel 1 (
            echo Warning: pywin32 post-install configuration may have failed
            echo You may need to run: python -m pywin32_postinstall -install
        ) else (
            echo pywin32 configuration completed
        )
    )
) else (
    echo Windows service modules available
)

:menu
echo.
echo ==========================================
echo   Task Management Client Service Manager
echo ==========================================
echo.
echo Please select client management option:
echo 1. Install Windows Service
echo 2. Uninstall Windows Service
echo 3. Start Service
echo 4. Stop Service
echo 5. Restart Service
echo 6. Check Service Status
echo 7. Run Client ^(Direct Mode^)
echo 8. Debug Service
echo 9. Exit
echo.

set /p choice=Please select [1-9]: 

if "%choice%"=="1" goto install_service
if "%choice%"=="2" goto uninstall_service
if "%choice%"=="3" goto start_service
if "%choice%"=="4" goto stop_service
if "%choice%"=="5" goto restart_service
if "%choice%"=="6" goto status_service
if "%choice%"=="7" goto run_direct
if "%choice%"=="8" goto debug_service
if "%choice%"=="9" goto end

echo Invalid selection. Please choose 1-9.
echo.
goto menu

:install_service
echo.
echo Installing Windows Service...
echo.
echo ⚠️  Note: Installing Windows Service requires Administrator privileges
echo    If installation fails, please run this batch file as Administrator
echo.

REM Check if running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: This operation requires Administrator privileges
    echo.
    echo Please right-click on client.bat and select "Run as administrator"
    echo Then try installing the service again.
    echo.
    timeout /t 2 /nobreak >nul
    goto menu
)

echo ✓ Administrator privileges detected
echo Installing service...

cd ..
%PYTHON_EXE% -m client.service install
set INSTALL_RESULT=%errorlevel%
cd client
if %INSTALL_RESULT% neq 0 (
    echo.
    echo ❌ Service installation failed
    echo.
    echo Common solutions:
    echo 1. Ensure you are running as Administrator
    echo 2. Check if the service name is already in use
    echo 3. Verify all Python dependencies are installed
    echo 4. Check Windows Event Log for detailed error information
) else (
    echo.
    echo ✓ Service installed successfully
    echo.
    echo Verifying installation...
    sc query WebGraphicsService >nul 2>&1
    if errorlevel 1 (
        echo ⚠️  Warning: Service installation reported success but service is not found
        echo This may indicate a partial installation failure.
    ) else (
        echo ✓ Service verification successful
        echo You can now use option 3 to start the service
        echo Or use Windows Services Manager ^(services.msc^)
    )
)
echo.
goto menu

:uninstall_service
echo.
echo Uninstalling Windows Service...
echo.
echo ⚠️  Note: Uninstalling Windows Service requires Administrator privileges
echo    If uninstallation fails, please run this batch file as Administrator
echo.

REM Check if running as administrator
net session >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: This operation requires Administrator privileges
    echo.
    echo Please right-click on client.bat and select "Run as administrator"
    echo Then try uninstalling the service again.
    echo.
    timeout /t 2 /nobreak >nul
    goto menu
)

echo ✓ Administrator privileges detected
echo Uninstalling service...

cd ..
%PYTHON_EXE% -m client.service uninstall
set UNINSTALL_RESULT=%errorlevel%
cd client
if %UNINSTALL_RESULT% neq 0 (
    echo.
    echo ❌ Service uninstallation failed
    echo.
    echo Common solutions:
    echo 1. Ensure you are running as Administrator
    echo 2. Stop the service first if it's running
    echo 3. Check Windows Event Log for detailed error information
) else (
    echo.
    echo ✓ Service uninstalled successfully
    echo.
    echo Service and configuration files have been removed
)
echo.
goto menu

:start_service
echo.
echo Starting Windows Service...
echo Service Name: WebGraphicsService
echo.

REM First check if service exists
sc query WebGraphicsService >nul 2>&1
if errorlevel 1 (
    echo ERROR: Service WebGraphicsService does not exist
    echo.
    echo The service may not be installed properly.
    echo Please try installing the service first - option 1.
    echo.
    timeout /t 2 /nobreak >nul
    goto menu
)

echo Service exists, attempting to start...
net start WebGraphicsService
if errorlevel 1 (
    echo Service start failed
    echo.
    echo Checking service status for more details...
    sc query WebGraphicsService
    echo.
    echo Checking Windows Event Log for service errors...
    echo Recent service-related errors:
    wevtutil qe Application /c:5 /rd:true /f:text /q:"*[System[Provider[@Name='Python Service'] or Provider[@Name='WebGraphicsService']]]" 2>nul
    if errorlevel 1 (
        echo No specific service errors found in Application log
        echo Checking System log...
        wevtutil qe System /c:5 /rd:true /f:text /q:"*[System[Provider[@Name='Service Control Manager'] and EventID=7034]]" 2>nul
    )
    echo.
    echo Common solutions:
    echo 1. Check if the service is already running
    echo 2. Verify all dependencies are available
    echo 3. Check Windows Event Viewer for detailed error logs
    echo 4. Ensure Python path and modules are accessible
    echo 5. Try running the service in debug mode using option 7
    echo.
    timeout /t 3 /nobreak >nul
) else (
    echo Service started successfully
)
echo.
goto menu

:stop_service
echo.
echo Stopping Windows Service...
net stop WebGraphicsService
if errorlevel 1 (
    echo ❌ Service stop failed
) else (
    echo ✓ Service stopped successfully
)
echo.
goto menu

:restart_service
echo.
echo Restarting Windows Service...
net stop WebGraphicsService
timeout /t 2 /nobreak >nul
net start WebGraphicsService
if errorlevel 1 (
    echo ❌ Service restart failed
) else (
    echo ✓ Service restarted successfully
)
echo.
goto menu

:status_service
echo.
echo Checking Service Status...
echo Service Name: WebGraphicsService
echo.

REM Check if service exists
sc query WebGraphicsService >nul 2>&1
if errorlevel 1 (
    echo ❌ Service 'WebGraphicsService' does not exist
    echo.
    echo The service is not installed. Use option 1 to install it.
) else (
    echo ✓ Service exists. Detailed status:
    echo.
    sc query WebGraphicsService
    echo.
    
    REM Check configuration directory
    if exist "C:\WebGraphicsService\config.json" (
        echo ✓ Configuration file exists: C:\WebGraphicsService\config.json
        echo Configuration:
        type "C:\WebGraphicsService\config.json"
    ) else (
        echo ⚠️  Configuration file not found: C:\WebGraphicsService\config.json
    )
)
echo.
goto menu

:run_direct
echo.
echo Starting client process ^(Direct Mode^)...
echo Press Ctrl+C to stop the client
echo.
echo Client name and server URL will be auto-detected
cd ..
%PYTHON_EXE% -m client.client_runner
cd client
echo.
echo Client process stopped.
echo.
goto menu

:debug_service
echo.
echo ========================================
echo Debugging service startup...
echo ========================================
echo.

REM First check service config  
echo Step 1: Checking service configuration...
%PYTHON_EXE% client\service.py check-config 2>nul
echo.

REM Test import dependencies
echo Step 2: Testing Python dependencies...
%PYTHON_EXE% -c "import sys; print('Python path:'); [print('  ', p) for p in sys.path[:5]]" 2>nul
echo.

echo Testing imports:
cd ..
%PYTHON_EXE% -c "from client.client_runner import TaskClientRunner; print('✓ TaskClientRunner import: OK')" 2>nul
if errorlevel 1 (
    echo ❌ TaskClientRunner import failed
    %PYTHON_EXE% -c "from client.client_runner import TaskClientRunner" 
    cd client
    timeout /t 3 /nobreak >nul
    goto menu
) 
cd client 

%PYTHON_EXE% -c "import requests; print('✓ requests import: OK')" 2>nul
if errorlevel 1 (
    echo ❌ requests module missing, installing...
    %PYTHON_EXE% -m pip install requests
)

%PYTHON_EXE% -c "import socketio; print('✓ socketio import: OK')" 2>nul
if errorlevel 1 (
    echo ❌ socketio module missing, installing...
    %PYTHON_EXE% -m pip install python-socketio
)

echo.
REM Test service initialization without actual service
echo Step 3: Testing service initialization...
%PYTHON_EXE% client\service.py debug 2>nul
echo.

echo Step 4: Recent Event Log errors...
wevtutil qe Application /c:5 /rd:true /f:text /q:"*[System[Provider[@Name='WebGraphicsService'] and TimeCreated[timediff(@SystemTime) <= 3600000]]]" 2>nul

echo.
echo Debug completed. Check the output above for any errors.
timeout /t 3 /nobreak >nul
goto menu

:end
echo.
echo Client manager completed.
