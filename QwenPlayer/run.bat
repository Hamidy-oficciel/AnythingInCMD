@echo off
setlocal
pushd "%~dp0"

where python >nul 2>nul && set "PY=python" || (where py >nul 2>nul && set "PY=py -3")
if not defined PY (
    echo Python 3.10+ is required but was not found on PATH.
    echo Install it from https://python.org and tick "Add python.exe to PATH".
    pause
    exit /b 1
)

%PY% -c "import yt_dlp" >nul 2>nul
if errorlevel 1 (
    echo Installing yt-dlp \(first run only, ~5 MB\)...
    %PY% -m pip install --quiet yt-dlp
    if errorlevel 1 (
        echo Could not install yt-dlp. Try: %PY% -m pip install yt-dlp
        pause
        exit /b 1
    )
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo FFmpeg was not found on PATH. Install it \(e.g. "winget install Gyan.FFmpeg"\)
    echo or copy ffmpeg.exe and ffplay.exe into the QwenPlayer folder.
    pause
    exit /b 1
)

set "PYTHONPATH=%CD%\src"
title QwenPlayer
%PY% -m qwenplayer %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%
