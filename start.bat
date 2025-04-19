@echo off
chcp 65001 > nul
setlocal enabledelayedexpansion
title LastOasisManager Launcher
color 0B

REM =============================================================================================
echo.
echo   ██╗      █████╗ ███████╗████████╗     ██████╗  █████╗ ███████╗██╗███████╗
echo   ██║     ██╔══██╗██╔════╝╚══██╔══╝    ██╔═══██╗██╔══██╗██╔════╝██║██╔════╝
echo   ██║     ███████║███████╗   ██║       ██║   ██║███████║███████╗██║███████╗
echo   ██║     ██╔══██║╚════██║   ██║       ██║   ██║██╔══██║╚════██║██║╚════██║
echo   ███████╗██║  ██║███████║   ██║       ╚██████╔╝██║  ██║███████║██║███████║
echo   ╚══════╝╚═╝  ╚═╝╚══════╝   ╚═╝        ╚═════╝ ╚═╝  ╚═╝╚══════╝╚═╝╚══════╝
echo.
echo   ███╗   ███╗ █████╗ ███╗   ██╗ █████╗  ██████╗ ███████╗██████╗ 
echo   ████╗ ████║██╔══██╗████╗  ██║██╔══██╗██╔════╝ ██╔════╝██╔══██╗
echo   ██╔████╔██║███████║██╔██╗ ██║███████║██║  ███╗█████╗  ██████╔╝
echo   ██║╚██╔╝██║██╔══██║██║╚██╗██║██╔══██║██║   ██║██╔══╝  ██╔══██╗
echo   ██║ ╚═╝ ██║██║  ██║██║╚═╝ ██║██║  ██║╚██████╗███████╗██████╔╝
echo   ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚═════╝
echo.
echo =============================================================================================
echo  This script launches the LastOasisManager application with proper environment setup
echo =============================================================================================
echo.

REM Define application modes
set "MODE_CLI=1"
set "MODE_GUI=2"
set "APP_MODE=0"

REM Define colors for console output
set "INFO_COLOR=color 0B"
set "SUCCESS_COLOR=color 0A"
set "WARNING_COLOR=color 0E"
set "ERROR_COLOR=color 0C"
set "RESET_COLOR=color 0B"

REM Store the script's directory path for absolute path references
set "SCRIPT_DIR=%~dp0"
set "VENV_PATH=%SCRIPT_DIR%.venv"
set "VENV_ACTIVATE=%VENV_PATH%\Scripts\activate.bat"
set "CLI_SCRIPT=%SCRIPT_DIR%LastOasisManager.py"
set "GUI_SCRIPT=%SCRIPT_DIR%main_gui.py"
set "EXIT_CODE=0"

echo [%time%] ▶ LastOasisManager launcher initializing...
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                     ENVIRONMENT VALIDATION                      ║
echo ╚════════════════════════════════════════════════════════════════════╝

REM Check if virtual environment exists
if not exist "%VENV_PATH%" (
    %ERROR_COLOR%
    echo [%time%] ✖ [ERROR] Virtual environment not found at: %VENV_PATH%
    echo         Please run setup script or create virtual environment before running this script.
    pause
    exit /b 1
)

REM Check if activation script exists
if not exist "%VENV_ACTIVATE%" (
    %ERROR_COLOR%
    echo [%time%] ✖ [ERROR] Virtual environment activation script not found at: %VENV_ACTIVATE%
    echo         The virtual environment may be corrupted. Please recreate it.
    pause
    exit /b 1
)

REM Check if Python scripts exist
if not exist "%CLI_SCRIPT%" (
    %ERROR_COLOR%
    echo [%time%] ✖ [ERROR] CLI application script not found at: %CLI_SCRIPT%
    echo         Please ensure the application files are installed correctly.
    pause
    exit /b 1
)

if not exist "%GUI_SCRIPT%" (
    %ERROR_COLOR%
    echo [%time%] ✖ [ERROR] GUI application script not found at: %GUI_SCRIPT%
    echo         Please ensure the application files are installed correctly.
    pause
    exit /b 1
)

%INFO_COLOR%
echo [%time%] ✓ Environment validation complete
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                    SELECT OPERATION MODE                        ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo.
echo  Please select the mode you want to run:
echo.
echo  [1] Command Line Interface (CLI) Mode
echo  [2] Graphical User Interface (GUI) Mode
echo.

:mode_selection
set /p APP_MODE="Enter your choice (1 or 2): "

if "%APP_MODE%"=="%MODE_CLI%" (
    echo.
    echo [%time%] ✓ Selected CLI Mode
    set "SELECTED_SCRIPT=%CLI_SCRIPT%"
) else if "%APP_MODE%"=="%MODE_GUI%" (
    echo.
    echo [%time%] ✓ Selected GUI Mode
    set "SELECTED_SCRIPT=%GUI_SCRIPT%"
) else (
    %WARNING_COLOR%
    echo [%time%] ⚠ Invalid selection. Please enter 1 for CLI or 2 for GUI.
    %INFO_COLOR%
    goto :mode_selection
)

echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                        LAUNCHING APP                            ║
echo ╚════════════════════════════════════════════════════════════════════╝

REM Activate virtual environment
echo [%time%] ⚡ Activating Python virtual environment...
call "%VENV_ACTIVATE%"
if errorlevel 1 (
    %ERROR_COLOR%
    echo [%time%] ✖ [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

%INFO_COLOR%
echo [%time%] ✓ Virtual environment activated successfully

REM Optional: Export requirements (commented out by default)
REM echo [%time%] Exporting requirements list...
REM pip freeze > "%SCRIPT_DIR%requirements.txt"

REM Run the selected Python script
if "%APP_MODE%"=="%MODE_CLI%" (
    echo [%time%] ⚡ Starting LastOasisManager in CLI mode...
) else (
    echo [%time%] ⚡ Starting LastOasisManager in GUI mode...
)
echo.
python "%SELECTED_SCRIPT%"
set EXIT_CODE=%errorlevel%
echo.

REM Deactivate virtual environment
echo [%time%] ⚡ Deactivating Python virtual environment...
call deactivate

REM Check Python script exit code
if %EXIT_CODE% neq 0 (
    %WARNING_COLOR%
    echo [%time%] ⚠ [WARNING] LastOasisManager exited with code: %EXIT_CODE%
) else (
    %SUCCESS_COLOR%
    echo [%time%] ✓ LastOasisManager completed successfully.
)

%INFO_COLOR%
echo.
echo ╔════════════════════════════════════════════════════════════════════╗
echo ║                      LAUNCHER COMPLETED                         ║
echo ╚════════════════════════════════════════════════════════════════════╝
echo [%time%] ■ LastOasisManager launcher finished.
pause
%RESET_COLOR%
exit /b %EXIT_CODE%
