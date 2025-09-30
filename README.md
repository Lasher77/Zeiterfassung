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

### Zusatzpakete für den PDF-Export (WeasyPrint):
- Für den WeasyPrint-Export werden zusätzliche **GTK-/Pango-Bibliotheken** benötigt.
- Installationsbeispiele:
  - **macOS (Homebrew):** `brew install pango gdk-pixbuf libffi`
    
    > 💡 **Hinweis für Apple-Silicon-/Homebrew-Installationen:** WeasyPrint benötigt Zugriff auf die von Homebrew installierten Bibliotheken. Setze deshalb vor dem Start von `server.py` die Variablen `DYLD_LIBRARY_PATH` und `DYLD_FALLBACK_LIBRARY_PATH`, z. B.:
    > 
    > ```bash
    > export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH}"
    > export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_FALLBACK_LIBRARY_PATH}"
    > ```
    > 
    > Hinterlege diese Exports dauerhaft in Deiner Shell-Konfiguration (z. B. `~/.zshrc`, `~/.bash_profile`) oder im Startskript, damit sie bei jedem Start verfügbar sind. Weitere Details findest Du in der [WeasyPrint-Dokumentation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#macos).
  - **Debian/Ubuntu (apt):** `sudo apt update && sudo apt install libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libcairo2`
  - **Fedora/RHEL (dnf):** `sudo dnf install pango gdk-pixbuf2 cairo libffi`
- Weitere Hinweise liefert die offizielle WeasyPrint-Dokumentation: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting

## 🧪 WeasyPrint-Abhängigkeits-Check

Führe vor dem ersten Start (oder nach Änderungen an Deinem System) den Check aus:

```bash
python check_weasyprint_dependencies.py
```

- **✅ Erfolgreich:** Starte anschließend wie gewohnt den Server (`python server.py` oder das Startskript).
- **❌ Fehlerausgabe:** Folge den im Skript angezeigten Plattform-Hinweisen (z. B. `apt`/`dnf`-Pakete unter Linux, `brew install`
  unter macOS inklusive der Umgebungsvariablen `DYLD_LIBRARY_PATH`/`DYLD_FALLBACK_LIBRARY_PATH`, GTK-Installer und `PATH`-Anpassung
  unter Windows).
- Wiederhole den Check, bis keine Fehlermeldungen mehr angezeigt werden. Erst dann ist der PDF-Export mit WeasyPrint zuverlässig
  nutzbar.

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

## 📡 **API-Endpunkte für Berichte**

### `GET /api/reports/overview/<year>/<month>`
- **Parameter**
  - `year`: Vierstellige Jahreszahl (z. B. `2024`)
  - `month`: Monat als Zahl `1-12`
- **Rückgabe**
  - JSON-Objekt mit `year`, `month` und einer Liste `employees`
  - Jedes Element in `employees` enthält die Stammdaten unter `employee`, alle Monatseinträge (`entries`) sowie eine `summary`
  - Die `summary` liefert u. a. `total_hours`, `work_days`, `vacation_days`, `sick_days`, `total_commission`, `total_duftreise_bis_18`, `total_duftreise_ab_18` und `contract_hours_month`
- **Verwendung**
  - Wird vom Frontend für die Übersicht im Reiter **Auswertungen** genutzt

### `GET /api/reports/overview/<year>/<month>/export`
- **Parameter**: identisch zu oben
- **Rückgabe**
  - CSV-Datei mit Kopfzeile und aggregierten Monatswerten je aktivem Mitarbeitenden
  - Der Download wird als Dateianhang (`Content-Disposition: attachment`) bereitgestellt
- **Verwendung**
  - Das Frontend startet über den Button **CSV Export** einen Download für den ausgewählten Zeitraum

## 🛠 **Problemlösung**

### **"Python nicht gefunden"**
- Python von https://python.org installieren
- Bei Installation "Add to PATH" aktivieren

### **"Port bereits belegt"**
- Anderen Port per Umgebungsvariable setzen, z.B.: `PORT=5002 ./start.sh`

### **"ImportError: libgobject-2.0-0 not found" beim Start von `server.py`**
- Ursache: Die für WeasyPrint erforderlichen GTK-/Pango-Bibliotheken fehlen.
- Lösung: Installiere die Pakete wie oben beschrieben (z. B. `brew install pango gdk-pixbuf libffi`, `sudo apt install libpango-1.0-0 libgdk-pixbuf2.0-0 libffi-dev libcairo2` oder `sudo dnf install pango gdk-pixbuf2 cairo libffi`).
- Prüfe ggf. die WeasyPrint-Troubleshooting-Seite: https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#troubleshooting
- **Apple Silicon/macOS Homebrew:** Setze zusätzlich dauerhaft `DYLD_LIBRARY_PATH` und `DYLD_FALLBACK_LIBRARY_PATH` (z. B. in `~/.zshrc`) auf `/opt/homebrew/lib`, damit WeasyPrint die benötigten Bibliotheken findet. Details siehe [WeasyPrint-Dokumentation](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#macos).
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
