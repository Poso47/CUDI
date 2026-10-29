@echo off
chcp 65001 >nul
set PYTHONUTF8=1
title CUDI Video
cd /d "%~dp0"

rem Python finden (python oder py-Launcher)
set PY=python
%PY% --version >nul 2>nul || set PY=py -3
%PY% --version >nul 2>nul || (
    echo Python fehlt. Bitte von https://www.python.org installieren ^(Haken bei "Add to PATH"^).
    pause
    exit /b 1
)

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ffmpeg fehlt. Installation mit:  winget install Gyan.FFmpeg
    echo Danach dieses Fenster schliessen und neu starten.
    pause
    exit /b 1
)

%PY% -c "import edge_tts, fastapi, PIL, numpy, yaml, bs4" >nul 2>nul
if errorlevel 1 (
    echo Installiere Python-Pakete ...
    %PY% -m pip install -r cudi_video\requirements.txt || (pause & exit /b 1)
)

echo.
echo CUDI Video startet auf http://localhost:8000
echo Vom Handy im selben WLAN: http://IP-DIESES-PCS:8000  (IP mit "ipconfig" anzeigen)
echo Tipp: Zugangscode setzen mit  set CUDI_VIDEO_TOKEN=deinCode  vor dem Start.
echo Fragt die Windows-Firewall nach Zugriff: "Zulassen" waehlen, sonst kann das Handy nicht verbinden.
echo Bei Problemen: CUDI_VIDEO_TEST.bat ausfuehren.
echo.
start "" http://localhost:8000
%PY% -m cudi_video web --port 8000
pause
