@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Create the project .venv first. See README.md.
    goto failed
)
if not exist ".venv-marker\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m venv .venv-marker
    if errorlevel 1 goto failed
)
set "PYTHON=.venv-marker\Scripts\python.exe"
"%PYTHON%" -m pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto failed
"%PYTHON%" -m pip install -r requirements-marker.lock
if errorlevel 1 goto failed
"%PYTHON%" -m pip check
if errorlevel 1 goto failed
echo Marker installed. Models download into model\ on the first conversion.
echo Run scripts\prepare-marker.bat to convert the local paper.
exit /b 0
:failed
echo Installation failed. No application data was replaced.
pause
exit /b 1
