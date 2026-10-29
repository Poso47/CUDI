@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title CUDI Video - Selbsttest
cd /d "%~dp0"
set PY=python
%PY% --version >nul 2>nul || set PY=py -3
%PY% -m cudi_video check
echo.
pause
