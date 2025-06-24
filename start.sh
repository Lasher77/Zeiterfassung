#!/bin/bash

echo "========================================"
echo "   Arbeitszeiterfassung mit SQLite"
echo "========================================"
echo

# Prüfe ob Python installiert ist
if ! command -v python3 &> /dev/null; then
    echo "FEHLER: Python3 ist nicht installiert!"
    echo "Bitte installieren Sie Python3:"
    echo "  macOS: brew install python3"
    echo "  Ubuntu: sudo apt install python3 python3-pip"
    echo
    exit 1
fi

echo "Python3 gefunden. Starte Server..."
echo

# Installiere Abh\xE4ngigkeiten falls nicht vorhanden
pip3 install -r requirements.txt > /dev/null 2>&1

# Port setzen (übernimmt vorhandene PORT-Variable oder nutzt 5001)
PORT=${PORT:-5001}
export PORT

# Starte den Server
echo "Server startet auf http://localhost:$PORT"
echo
echo "WICHTIG: Lassen Sie dieses Terminal offen!"
echo "Zum Beenden drücken Sie Strg+C"
echo
echo "Öffne automatisch den Browser..."
sleep 2

# Öffne Browser (funktioniert auf macOS und Linux)
if command -v open &> /dev/null; then
    open http://localhost:$PORT
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:$PORT
fi

python3 server.py

