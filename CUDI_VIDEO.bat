@echo off
chcp 65001 >nul
title CUDI Video
cd /d "%~dp0"

where ffmpeg >nul 2>nul
if errorlevel 1 (
    echo ffmpeg fehlt. Installation mit:  winget install Gyan.FFmpeg
    echo Danach dieses Fenster schliessen und neu starten.
    pause
    exit /b 1
)

python -c "import edge_tts, fastapi, PIL" >nul 2>nul
if errorlevel 1 (
    echo Installiere Python-Pakete ...
    python -m pip install -r cudi_video\requirements.txt || (pause & exit /b 1)
)

echo.
echo CUDI Video startet auf http://localhost:8000
echo Vom Handy im selben WLAN: http://IP-DIESES-PCS:8000  (IP mit "ipconfig" anzeigen)
echo Tipp: Zugangscode setzen mit  set CUDI_VIDEO_TOKEN=deinCode  vor dem Start.
echo.
start "" http://localhost:8000
python -m cudi_video web --port 8000
pause
