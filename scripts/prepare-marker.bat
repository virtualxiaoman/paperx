@echo off
setlocal EnableExtensions
cd /d "%~dp0.."
if not exist ".venv-marker\Scripts\python.exe" (
    echo Run scripts\install-marker.bat first.
    goto failed
)
.venv\Scripts\python.exe scripts\prepare_samples.py --parser marker
if errorlevel 1 goto failed
echo Marker blocks published. Start scripts\start.bat or refresh the browser.
exit /b 0
:failed
echo Conversion failed. Check data\marker\ for worker.log. Existing samples are retained.
pause
exit /b 1
