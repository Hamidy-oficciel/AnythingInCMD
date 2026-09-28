@echo off
setlocal
pushd "%~dp0"

call scripts\make_venv.bat
if errorlevel 1 goto failed

call scripts\check_ffmpeg.bat
if errorlevel 1 goto failed

set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m youtubecmd.player %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:failed
popd
pause
exit /b 1