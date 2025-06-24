# Arbeitszeiterfassung mit SQLite-Datenbank

## 🎯 **Überblick**

Diese professionelle Arbeitszeiterfassung nutzt eine **SQLite-Datenbank** für sichere und zuverlässige Datenspeicherung. Die Anwendung läuft lokal auf Ihrem Computer und bietet alle Funktionen der ursprünglichen Excel-Tabelle in einer modernen Web-Oberfläche.

**Hinweis:** Die Datenbankdatei `zeiterfassung.db` wird beim Start des Servers automatisch angelegt und ist deshalb nicht Teil des Git-Repositories.

## ✅ **Vorteile der SQLite-Version**

- **🔒 Sichere Datenspeicherung** - Keine Datenverluste durch Browser-Cache
- **📊 Professionelle Datenbank** - Strukturierte, konsistente Daten
- **🚀 Bessere Performance** - Schnellere Abfragen und Berechnungen
- **💾 Backup-fähig** - Einfache Sicherung der `zeiterfassung.db` Datei
- **⚙️ Automatisch generiert** - Die Datei `zeiterfassung.db` wird beim Start des Servers erstellt und sollte nicht per Git versioniert werden
- **🔄 Mehrbenutzerfähig** - Vorbereitet für Netzwerk-Zugriff
- **📈 Skalierbar** - Kann später erweitert werden

## 📋 **Systemvoraussetzungen**

### Windows:
- **Python 3.7+** (Download: https://python.org)
- Webbrowser (Chrome, Firefox, Edge, Safari)

### macOS:
- **Python 3.7+** (meist vorinstalliert oder via Homebrew)
- Webbrowser (Chrome, Firefox, Safari)

### Linux:
- **Python 3.7+** und **pip3**
- Webbrowser (Chrome, Firefox)

## 🚀 **Installation & Start**

### **Einfacher Start:**

1. **Ordner entpacken** an gewünschten Ort
2. **Doppelklick** auf das entsprechende Startscript:
   - **Windows:** `start.bat`
   - **macOS/Linux:** `start.sh`
3. **Fertig!** Browser öffnet automatisch

### **Manueller Start:**

```bash
# Terminal/Kommandozeile öffnen
cd pfad/zum/zeiterfassung-ordner

# Abhängigkeiten installieren (einmalig)
pip install -r requirements.txt

# Server starten
python server.py

# Browser öffnen: http://localhost:5001
```

Port ändern:
```bash
PORT=5002 python server.py
```

Debug-Modus aktivieren:
```bash
FLASK_DEBUG=1 python server.py
```

## 📁 **Dateien im Paket**

```
zeiterfassung-sqlite/
├── server.py          # Python-Backend mit SQLite
├── index.html         # Web-Frontend
├── app.js            # JavaScript-Logik
├── start.bat         # Windows-Startscript
├── start.sh          # macOS/Linux-Startscript
├── README.md         # Diese Anleitung
└── zeiterfassung.db  # SQLite-Datenbank (wird automatisch erstellt)
```

## 🎮 **Bedienung**

### **1. Dashboard**
- Übersicht aller Mitarbeiter
- Aktuelle Statistiken
- Schnellzugriff auf wichtige Daten

### **2. Zeiterfassung**
- **Mitarbeiter auswählen** aus Dropdown
- **Monat/Jahr** einstellen
- **Kalenderansicht** wie in Excel
- **Klick auf Tag** öffnet Eingabedialog

### **3. Eingabedialog (vergrößert)**
- **Arbeitszeit:** Start/Ende/Pause
- **Urlaub/Krank:** Überschreibt andere Einträge
- **Duftreisen:** Bis 18h / Ab 18h (mehrfach möglich)
- **Provision:** Wird angezeigt (später automatisch berechnet)
- **Notizen:** Zusätzliche Informationen
- **Beschäftigungszeitraum:** Start- und Enddatum des Mitarbeiters erfassen

### **4. Besonderheiten**
- **Samstag ist Arbeitstag** (Einzelhandel)
- **Duftreisen unabhängig** von Arbeitszeit
- **Urlaub/Krank** macht andere Einträge irrelevant
- **Automatische Speicherung** in SQLite-Datenbank
- **Beschäftigungszeitraum** eintragbar (Start- und Enddatum)
- **Hinweis bei falschem Datum**: Zeitbuchungen außerhalb dieses Zeitraums
  zeigen eine verständliche Meldung an

## 🔧 **Erweiterte Funktionen**

### **Datenbank-Backup:**
```bash
# Einfach die Datei kopieren
cp zeiterfassung.db zeiterfassung_backup_2025-06-23.db
```

### **Datenbank-Wiederherstellung:**
```bash
# Backup-Datei zurückkopieren
cp zeiterfassung_backup_2025-06-23.db zeiterfassung.db
```

### **Netzwerk-Zugriff (optional):**
Server auf allen Netzwerkschnittstellen starten:
```bash
PORT=5001 python server.py
```
Dann von anderen PCs erreichbar unter: `http://[IP-ADRESSE]:5001`

## 🛠 **Problemlösung**

### **"Python nicht gefunden"**
- Python von https://python.org installieren
- Bei Installation "Add to PATH" aktivieren

### **"Port bereits belegt"**
- Anderen Port per Umgebungsvariable setzen, z.B.: `PORT=5002 ./start.sh`
- In `app.js` API_BASE_URL entsprechend anpassen: `http://localhost:5002/api`

### **"Keine Verbindung zum Server"**
- Prüfen ob `server.py` läuft
- Browser-Cache leeren (Strg+F5)
- Firewall/Antivirus prüfen

### **Datenbank-Probleme**
- `zeiterfassung.db` löschen (wird neu erstellt)
- Backup einspielen falls vorhanden

## 📞 **Support**

Bei Problemen:
1. **Startscript verwenden** (automatische Fehlererkennung)
2. **Terminal-Ausgabe prüfen** (Fehlermeldungen)
3. **Browser-Konsole öffnen** (F12 → Console)
4. **Backup der Datenbank erstellen** vor Änderungen

## 🔄 **Migration von localStorage**

Falls Sie die alte localStorage-Version verwendet haben:
1. Alte Daten im Browser exportieren (falls möglich)
2. Neue SQLite-Version starten
3. Daten manuell neu eingeben (sicherer)

## 🎯 **Nächste Schritte**

Die Anwendung ist bereit für:
- **Automatische Provisionsberechnung** basierend auf Umsatz
- **PDF-Export** für Lohnbuchhaltung
- **Erweiterte Berichte** und Statistiken
- **Netzwerk-Deployment** für mehrere Benutzer

---

**Die Arbeitszeiterfassung ist jetzt professionell und sicher mit SQLite-Datenbank!** 🎉


## Lizenz
Die Anwendung steht unter der MIT-Lizenz. Siehe [LICENSE](LICENSE) für weitere Informationen.
