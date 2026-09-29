@echo off
setlocal
pushd "%~dp0"

call scripts\make_venv.bat
if errorlevel 1 goto failed

call scripts\check_ffmpeg.bat
if errorlevel 1 goto failed

".venv\Scripts\python.exe" native\build.py
if errorlevel 1 goto failed

set "PYTHONPATH=%CD%\src"
echo YouTubeCMD
echo.
echo Choose source video quality:
echo   1. 360p
echo   2. 480p
echo   3. 720p (recommended)
echo   4. 1080p
echo   5. Best available
set "VIDEO_QUALITY=720"
set /p "VIDEO_QUALITY_CHOICE=Select 1-5 [3]: "
if "%VIDEO_QUALITY_CHOICE%"=="1" set "VIDEO_QUALITY=360"
if "%VIDEO_QUALITY_CHOICE%"=="2" set "VIDEO_QUALITY=480"
if "%VIDEO_QUALITY_CHOICE%"=="4" set "VIDEO_QUALITY=1080"
if "%VIDEO_QUALITY_CHOICE%"=="5" set "VIDEO_QUALITY=best"
set "STREAM_FILE=%TEMP%\YouTubeCMD-stream-%RANDOM%-%RANDOM%.json"
".venv\Scripts\python.exe" -m youtubecmd.extract %* --video-quality "%VIDEO_QUALITY%" > "%STREAM_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" goto finished
"bin\renderer.exe" --stream "%STREAM_FILE%" --mode terminal-pixel --quality high
set "EXIT_CODE=%ERRORLEVEL%"

:finished
if exist "%STREAM_FILE%" del /q "%STREAM_FILE%"
popd
exit /b %EXIT_CODE%

:failed
popd
pause
exit /b 1