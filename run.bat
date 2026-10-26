@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
set "PYTHONUTF8=1"

pushd "%~dp0" || exit /b 1
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_system.ps1"
set "RUN_EXIT_CODE=%ERRORLEVEL%"
popd

if not "%RUN_EXIT_CODE%"=="0" pause
exit /b %RUN_EXIT_CODE%
