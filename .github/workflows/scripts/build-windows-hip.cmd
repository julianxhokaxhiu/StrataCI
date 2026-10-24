@echo off
setlocal
call strata\tools\hip\build_windows.bat
exit /b %ERRORLEVEL%
