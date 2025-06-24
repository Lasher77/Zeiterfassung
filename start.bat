@echo off
echo ========================================
echo    Arbeitszeiterfassung mit SQLite
echo ========================================
echo.

REM Prüfe ob Python installiert ist
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo FEHLER: Python ist nicht installiert!
    echo Bitte installieren Sie Python von https://python.org
    echo.
    pause
    exit /b 1
)

echo Python gefunden. Starte Server...
echo.

REM Installiere Flask falls nicht vorhanden
pip install flask flask-cors >nul 2>&1

REM Port setzen (vorhandene PORT-Variable verwenden oder 5001)
if not defined PORT set PORT=5001

REM Starte den Server
echo Server startet auf http://localhost:%PORT%
echo.
echo WICHTIG: Lassen Sie dieses Fenster offen!
echo Zum Beenden druecken Sie Strg+C
echo.
echo Oeffne automatisch den Browser...
timeout /t 2 >nul
start http://localhost:%PORT%

python server.py

pause

