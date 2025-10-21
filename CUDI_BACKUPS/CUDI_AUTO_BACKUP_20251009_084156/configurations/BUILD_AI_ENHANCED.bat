@echo off
title CUDI AI-Enhanced Builder
echo.
echo ========================================
echo 🤖 CUDI AI-Enhanced Build System
echo ========================================
echo.

echo 🔍 Überprüfe Python Installation...
python --version
if errorlevel 1 (
    echo ❌ Python nicht gefunden!
    echo Bitte installiere Python 3.13 oder höher
    pause
    exit /b 1
)

echo.
echo 📦 Installiere AI-Dependencies...
pip install --upgrade pip
pip install -r requirements_ai_enhanced.txt

echo.
echo 🚀 Starte AI-Enhanced Build...
python build_ai_enhanced.py

echo.
if exist "CUDI_AI_Enhanced_Build\dist\CUDI_AI_Enhanced.exe" (
    echo ✅ BUILD ERFOLGREICH!
    echo.
    echo 🎉 CUDI AI-Enhanced wurde erfolgreich erstellt!
    echo 📍 Pfad: CUDI_AI_Enhanced_Build\dist\CUDI_AI_Enhanced.exe
    echo.
    echo 🤖 AI-Features enthalten:
    echo   • Machine Learning Integration
    echo   • Natural Language Processing
    echo   • Pattern Recognition
    echo   • Intelligent Code Generation
    echo   • Smart Learning Optimization
    echo.
    echo 🚀 Möchtest du CUDI AI-Enhanced jetzt starten? (J/N)
    set /p choice="> "
    if /i "%choice%"=="J" (
        echo.
        echo 🤖 Starte CUDI AI-Enhanced...
        cd "CUDI_AI_Enhanced_Build\dist"
        CUDI_AI_Enhanced.exe
    )
) else (
    echo ❌ BUILD FEHLGESCHLAGEN!
    echo Überprüfe die Fehlerausgabe oben.
    echo.
    echo 🔧 Fallback: Versuche minimalen Build...
    python build_minimal_exe.py
)

echo.
echo 📋 Build-Prozess abgeschlossen.
pause
