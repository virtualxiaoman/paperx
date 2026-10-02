@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
for %%I in ("%ROOT%") do set "ROOT=%%~fI"
pushd "%ROOT%" >nul 2>&1
if errorlevel 1 (
    echo Failed to enter project directory: %ROOT%
    exit /b 1
)

set "PYTHON=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo Missing .venv. Run: python -m venv .venv
    popd
    exit /b 1
)

where npm.cmd >nul 2>&1
if errorlevel 1 (
    echo npm was not found. Install Node.js 24+ first.
    popd
    exit /b 1
)

set "INSTALL=0"
set "SKIP_PREPARE=1"
set "OPEN_BROWSER=0"

:parse_args
if "%~1"=="" goto args_done
if /I "%~1"=="/install" set "INSTALL=1"
if /I "%~1"=="/prepare" set "SKIP_PREPARE=0"
if /I "%~1"=="/skip-prepare" set "SKIP_PREPARE=1"
if /I "%~1"=="/open-browser" set "OPEN_BROWSER=1"
shift
goto parse_args

:args_done
if not exist "data\samples\single-column\document.json" set "SKIP_PREPARE=0"
if "%INSTALL%"=="1" (
    echo Installing Python dependencies...
    call "%PYTHON%" -m pip install -r requirements.lock
    if errorlevel 1 goto failed

    echo Installing frontend dependencies...
    call npm.cmd --prefix web ci
    if errorlevel 1 goto failed
)

if "%SKIP_PREPARE%"=="0" (
    echo Preparing local PDF samples...
    call "%PYTHON%" scripts\prepare_samples.py --parser marker
    if errorlevel 1 goto failed
)

echo Starting backend at http://127.0.0.1:8000 ...
start "Paperx Backend" /D "%ROOT%" "%PYTHON%" -m uvicorn paperx.api:app --app-dir backend --host 127.0.0.1 --port 8000

echo Starting frontend at http://127.0.0.1:5173 ...
start "Paperx Frontend" /D "%ROOT%" npm.cmd --prefix web run dev -- --port 5173 --strictPort

if "%OPEN_BROWSER%"=="1" (
    timeout /t 2 /nobreak >nul
    start "" "http://127.0.0.1:5173"
)

echo.
echo Backend docs: http://127.0.0.1:8000/docs
echo Frontend:    http://127.0.0.1:5173
echo Close the two service windows to stop the project.
popd
exit /b 0

:failed
echo.
echo Startup failed. See the error above.
pause
popd
exit /b 1


