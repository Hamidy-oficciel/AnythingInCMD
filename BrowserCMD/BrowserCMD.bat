@echo off
setlocal EnableExtensions
pushd "%~dp0"

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>nul
    if errorlevel 1 goto missing_python
    set "PYTHON=python"
    set "PYTHON_ARGS="
)

%PYTHON% %PYTHON_ARGS% -c "import sys; raise SystemExit(sys.version_info < (3, 10))" >nul 2>nul
if errorlevel 1 goto old_python

if not exist ".venv\Scripts\python.exe" (
    %PYTHON% %PYTHON_ARGS% -m venv .venv
    if errorlevel 1 goto failed
)

".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" native\build.py
if errorlevel 1 goto failed
set "PYTHONPATH=%CD%\src"
".venv\Scripts\python.exe" -m browsercmd.cli %*
set "EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %EXIT_CODE%

:missing_python
echo Python 3.10 or newer is required. Install it and enable the Python launcher or PATH.
goto failed

:old_python
echo Python 3.10 or newer is required.
goto failed

:failed
set "EXIT_CODE=1"
popd
exit /b %EXIT_CODE%