@echo off
setlocal EnableExtensions EnableDelayedExpansion
pushd "%~dp0"
if not exist "..\bin" mkdir "..\bin"
where cl >nul 2>nul
if errorlevel 1 (
    set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
    if not exist "!VSWHERE!" (
        echo MSVC compiler was not found.
        popd
        exit /b 1
    )
    for /f "usebackq tokens=*" %%i in (`"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALL=%%i"
    if not defined VSINSTALL (
        echo MSVC C++ tools were not found.
        popd
        exit /b 1
    )
    call "!VSINSTALL!\Common7\Tools\VsDevCmd.bat" -arch=x64
    if errorlevel 1 (
        popd
        exit /b 1
    )
)
cl /nologo /O2 /W4 /WX /std:c++17 /EHsc /MT src\main.cpp /Fo..\bin\ /Fe:..\bin\renderer.exe
set "BUILD_RESULT=%ERRORLEVEL%"
popd
exit /b %BUILD_RESULT%