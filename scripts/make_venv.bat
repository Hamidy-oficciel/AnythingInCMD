@echo off
setlocal
set "PROJECT_ROOT=%~dp0.."
pushd "%PROJECT_ROOT%"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/.
        popd
        exit /b 1
    )
    set "PYTHON_CMD=python"
)

%PYTHON_CMD% -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 (
    echo Python 3.10 or newer is required. Install it from https://www.python.org/downloads/.
    popd
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    %PYTHON_CMD% -m venv .venv
    if errorlevel 1 (
        echo Could not create the Python virtual environment.
        popd
        exit /b 1
    )
)

".venv\Scripts\python.exe" -c "import yt_dlp" >nul 2>nul
if errorlevel 1 (
    echo Installing YouTubeCMD Python dependencies...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. Check your network connection.
        popd
        exit /b 1
    )
)

set "NATIVE_SOURCE=src\youtubecmd\_native_renderer.c"
set "NATIVE_MARKER=.venv\.native-renderer-source"
".venv\Scripts\python.exe" -c "import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); m=pathlib.Path(sys.argv[2]); h=hashlib.sha256(p.read_bytes()).hexdigest(); raise SystemExit(0 if m.exists() and m.read_text()==h else 1)" "%NATIVE_SOURCE%" "%NATIVE_MARKER%" >nul 2>nul
if errorlevel 1 (
    echo Building the optional native renderer...
    ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --no-deps -e .
    if errorlevel 1 (
        echo Native renderer build failed. YouTubeCMD can still use its Python fallback.
    ) else (
        ".venv\Scripts\python.exe" -c "import hashlib,pathlib,sys; p=pathlib.Path(sys.argv[1]); pathlib.Path(sys.argv[2]).write_text(hashlib.sha256(p.read_bytes()).hexdigest())" "%NATIVE_SOURCE%" "%NATIVE_MARKER%"
    )
)

popd
exit /b 0