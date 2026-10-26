@echo off
REM ============================================================
REM  CUDI starten - einfach doppelklicken.
REM  Beim ersten Start wird alles Noetige automatisch installiert
REM  (eigene Umgebung im Ordner .venv, dein System bleibt sauber).
REM  Optionen:  CUDI_STARTEN.bat --cli       (Chat im Terminal)
REM             CUDI_STARTEN.bat --diagnose  (Selbstdiagnose)
REM ============================================================
setlocal
cd /d "%~dp0"
title CUDI

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo Python wurde nicht gefunden.
    echo Bitte Python 3.10 oder neuer von https://www.python.org installieren
    echo und dabei "Add python.exe to PATH" anhaken. Danach diese Datei erneut starten.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Erster Start: CUDI wird eingerichtet ^(das dauert einige Minuten^) ...
    %PY% -m venv .venv
    if errorlevel 1 goto fehler
)

if not exist ".venv\cudi_installiert.txt" (
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements-core.txt
    if errorlevel 1 goto fehler
    echo installiert> ".venv\cudi_installiert.txt"
)

REM Claude-Schluessel in .env eingetragen? Dann das Claude-Paket nachinstallieren.
if exist ".env" (
    findstr /b /c:"ANTHROPIC_API_KEY=" ".env" >nul 2>nul
    if not errorlevel 1 (
        ".venv\Scripts\python.exe" -c "import anthropic" >nul 2>nul
        if errorlevel 1 ".venv\Scripts\python.exe" -m pip install "anthropic>=1.0.0"
    )
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 goto fehler
exit /b 0

:fehler
echo.
echo CUDI konnte nicht gestartet werden - die Meldung oben zeigt den Grund.
echo Hilfe: docs\user_guide.md  oder  CUDI_STARTEN.bat --diagnose
pause
exit /b 1
