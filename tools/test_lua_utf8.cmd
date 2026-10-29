@echo off
setlocal
cd /d "%~dp0.."
set "VBA_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`"%VBA_VSWHERE%" -all -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VBA_VSROOT=%%i"
if not defined VBA_VSROOT exit /b 2
call "%VBA_VSROOT%\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 2
if not exist build\checks mkdir build\checks
cl /nologo /W4 /EHsc /MT /DWIN32 /DHAVE_STDINT_H /D_WIN32_WINNT=0x0501 /Iwin32\lib\zlib /c src\common\Text.cpp /Fo:build\checks\Text.obj
if errorlevel 1 exit /b 1
cl /nologo /W4 /EHsc /MT /DWIN32 /DHAVE_STDINT_H /D_WIN32_WINNT=0x0501 /Iwin32\lib\zlib tests\lua_utf8_text_test.cpp build\checks\Text.obj /Fo:build\checks\lua_utf8_text_test.obj /Fe:build\checks\lua_utf8_text_test.exe /link gdi32.lib user32.lib
if errorlevel 1 exit /b 1
build\checks\lua_utf8_text_test.exe
if errorlevel 1 exit /b 1
python tools\prepare_lua_api_test.py
if errorlevel 1 exit /b 1
cl /nologo /W4 /EHsc /MT /DWIN32 tests\lua_api_test.cpp /Fo:build\checks\lua_api_test.obj /Fe:build\checks\lua_api_test.exe /link win32\lib\lua51.lib gdi32.lib user32.lib
if errorlevel 1 exit /b 1
build\checks\lua_api_test.exe
