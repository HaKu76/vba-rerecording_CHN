@echo off
setlocal
cd /d "%~dp0.."
python tests\check_localization.py --prepare-rc
if errorlevel 1 exit /b 1
set "VBA_VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`"%VBA_VSWHERE%" -all -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VBA_VSROOT=%%i"
if not defined VBA_VSROOT exit /b 2
call "%VBA_VSROOT%\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 2
rc /nologo /d_DEBUG /i build\checks /i fonts\fusion-pixel /i src\win32 /fo build\checks\original.res build\checks\original.rc
if errorlevel 1 exit /b 1
rc /nologo /d_DEBUG /i build\checks /i fonts\fusion-pixel /i src\win32 /fo build\checks\chinese.res src\win32\vba.rc
if errorlevel 1 exit /b 1
rc /nologo /d_DEBUG /i build\checks /i src\win32\7zip /fo build\checks\original-7zip.res build\checks\original-7zip.rc
if errorlevel 1 exit /b 1
rc /nologo /d_DEBUG /i build\checks /i src\win32\7zip /fo build\checks\chinese-7zip.res src\win32\7zip\7zip.rc
if errorlevel 1 exit /b 1
link /nologo /DLL /NOENTRY /MACHINE:X86 /OUT:build\checks\original-resources.dll build\checks\original.res build\checks\original-7zip.res
if errorlevel 1 exit /b 1
link /nologo /DLL /NOENTRY /MACHINE:X86 /OUT:build\checks\chinese-resources.dll build\checks\chinese.res build\checks\chinese-7zip.res
if errorlevel 1 exit /b 1
python tests\check_localization.py --compiled
