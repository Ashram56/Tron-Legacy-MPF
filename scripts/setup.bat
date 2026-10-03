@echo off
rem Installs the pinned toolchain on Windows (MPF, Godot, GMC, generated media): runs scripts\setup.py.
rem Usage (cmd, in the repo):  scripts\setup.bat [--monitor] [--dry-run] ...
where py >nul 2>nul
if %ERRORLEVEL%==0 (py -3 "%~dp0setup.py" %*) else (python "%~dp0setup.py" %*)
exit /b %ERRORLEVEL%
