#!/usr/bin/env python3
"""
Arbeitszeiterfassung Backend mit SQLite
"""

import sqlite3
import json
from datetime import datetime, date
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os

app = Flask(__name__)
CORS(app)  # Erlaube Cross-Origin Requests

# Datenbank-Pfad
DB_PATH = 'zeiterfassung.db'

def init_database():
    """Initialisiere SQLite-Datenbank mit Tabellen"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Mitarbeiter-Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            contract_hours INTEGER NOT NULL,
            has_commission BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            start_date DATE NOT NULL,
            end_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Bestehende Tabellen um fehlende Spalten erweitern
    cursor.execute('PRAGMA table_info(employees)')
    cols = [row[1] for row in cursor.fetchall()]
    if 'start_date' not in cols:
        cursor.execute('ALTER TABLE employees ADD COLUMN start_date DATE')
    if 'end_date' not in cols:
        cursor.execute('ALTER TABLE employees ADD COLUMN end_date DATE')
    
    # Zeiterfassung-Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date DATE NOT NULL,
            entry_type TEXT NOT NULL DEFAULT 'work',  -- work, vacation, sick
            start_time TIME,
            end_time TIME,
            pause_minutes INTEGER DEFAULT 0,
            commission REAL DEFAULT 0.0,
            duftreise_bis_18 INTEGER DEFAULT 0,
            duftreise_ab_18 INTEGER DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
    ''')
    
    # Umsatz-Tabelle
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS revenue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date DATE NOT NULL,
            amount REAL NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Provisionseinstellungen
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS commission_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            percentage REAL NOT NULL DEFAULT 0,
            monthly_max REAL NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('SELECT COUNT(*) FROM commission_settings')
    if cursor.fetchone()[0] == 0:
        cursor.execute('INSERT INTO commission_settings (id, percentage, monthly_max) VALUES (1, 0, 0)')

    # Provisionsschwellen
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='commission_thresholds'"
    )
    table_exists = cursor.fetchone() is not None

    def create_commission_thresholds_table():
        cursor.execute('''
            CREATE TABLE commission_thresholds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                weekday INTEGER NOT NULL,
                employee_count INTEGER NOT NULL,
                threshold REAL NOT NULL,
                valid_from DATE NOT NULL DEFAULT '1970-01-01',
                UNIQUE (weekday, employee_count, valid_from)
            )
        ''')

    if not table_exists:
        create_commission_thresholds_table()
    else:
        cursor.execute('PRAGMA table_info(commission_thresholds)')
        columns = [row[1] for row in cursor.fetchall()]
        needs_migration = 'valid_from' not in columns

        if not needs_migration:
            cursor.execute('PRAGMA index_list(commission_thresholds)')
            indexes = cursor.fetchall()
            has_desired_unique = False
            for index in indexes:
                if index[2]:  # unique index
                    idx_name = index[1]
                    cursor.execute(f"PRAGMA index_info('{idx_name}')")
                    idx_columns = [info[2] for info in cursor.fetchall()]
                    if idx_columns == ['weekday', 'employee_count', 'valid_from']:
                        has_desired_unique = True
                        break
            needs_migration = not has_desired_unique

        if needs_migration:
            cursor.execute('ALTER TABLE commission_thresholds RENAME TO commission_thresholds_old')
            create_commission_thresholds_table()
            if 'valid_from' in columns:
                cursor.execute('''
                    INSERT INTO commission_thresholds (id, weekday, employee_count, threshold, valid_from)
                    SELECT id, weekday, employee_count, threshold,
                           COALESCE(valid_from, '1970-01-01')
                    FROM commission_thresholds_old
                ''')
            else:
                cursor.execute('''
                    INSERT INTO commission_thresholds (id, weekday, employee_count, threshold, valid_from)
                    SELECT id, weekday, employee_count, threshold,
                           '1970-01-01'
                    FROM commission_thresholds_old
                ''')
            cursor.execute('DROP TABLE commission_thresholds_old')
        else:
            cursor.execute(
                "UPDATE commission_thresholds SET valid_from = '1970-01-01' WHERE valid_from IS NULL"
            )
    
    conn.commit()
    conn.close()
    print("Datenbank initialisiert!")

def get_db_connection():
    """Erstelle Datenbankverbindung"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Ermöglicht dict-ähnlichen Zugriff
    return conn

def compute_commission_for_date(date_str):
    """Berechne Provisionen für einen bestimmten Tag"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Umsatz des Tages
    rev = cursor.execute(
        'SELECT amount FROM revenue WHERE date = ?',
        (date_str,)
    ).fetchone()
    revenue = rev['amount'] if rev else 0

    # Globale Provisionseinstellungen
    settings = cursor.execute(
        'SELECT percentage, monthly_max FROM commission_settings WHERE id = 1'
    ).fetchone()
    percentage = settings['percentage'] if settings else 0
    monthly_max = settings['monthly_max'] if settings else 0

    # Mitarbeiter, die an diesem Tag gearbeitet haben und provisionsberechtigt sind
    entries = cursor.execute(
        '''
            SELECT te.id, te.employee_id, te.start_time, te.end_time,
                   te.pause_minutes
            FROM time_entries te
            JOIN employees e ON te.employee_id = e.id
            WHERE te.date = ?
              AND te.entry_type = 'work'
              AND te.start_time IS NOT NULL AND te.end_time IS NOT NULL
              AND e.has_commission = 1
        ''',
        (date_str,),
    ).fetchall()

    emp_hours = {}
    entry_ids = {}
    for row in entries:
        start = datetime.strptime(row['start_time'], '%H:%M')
        end = datetime.strptime(row['end_time'], '%H:%M')
        hours = (end - start).seconds / 3600 - (row['pause_minutes'] or 0) / 60
        emp_hours.setdefault(row['employee_id'], 0)
        emp_hours[row['employee_id']] += hours
        entry_ids[row['employee_id']] = row['id']

    employee_count = len(emp_hours)

    weekday = datetime.strptime(date_str, '%Y-%m-%d').weekday()
    th = cursor.execute(
        '''
            SELECT threshold FROM commission_thresholds
            WHERE weekday = ? AND employee_count = ? AND valid_from <= ?
            ORDER BY valid_from DESC
            LIMIT 1
        ''',
        (weekday, employee_count, date_str),
    ).fetchone()
    threshold = th['threshold'] if th else 0

    total_hours = sum(emp_hours.values())
    total_commission = 0
    if revenue >= threshold and total_hours > 0 and percentage > 0:
        total_commission = revenue * (percentage / 100.0)

    ids = list(entry_ids.values())

    for emp_id, hours in emp_hours.items():
        entry_id = entry_ids[emp_id]
        commission = 0
        if total_commission > 0:
            share = hours / total_hours if total_hours else 0
            raw_commission = total_commission * share

            y, m, _ = date_str.split('-')
            month_total = cursor.execute(
                '''
                    SELECT SUM(commission) AS total FROM time_entries
                    WHERE employee_id = ?
                      AND strftime('%Y', date) = ?
                      AND strftime('%m', date) = ?
                      AND date != ?
                ''',
                (emp_id, y, m, date_str),
            ).fetchone()
            month_total = month_total['total'] or 0
            allowed = max(0, monthly_max - month_total)
            commission = min(raw_commission, allowed)

        cursor.execute(
            'UPDATE time_entries SET commission = ? WHERE id = ?',
            (round(commission, 2), entry_id),
        )

    # Alle anderen Einträge des Tages auf 0 setzen
    if ids:
        placeholders = ','.join('?' for _ in ids)
        cursor.execute(
            f'UPDATE time_entries SET commission = 0 WHERE date = ? '
            f'AND id NOT IN ({placeholders})',
            [date_str] + ids,
        )
    else:
        cursor.execute(
            'UPDATE time_entries SET commission = 0 WHERE date = ?', (date_str,)
        )

    conn.commit()
    conn.close()

# API Endpunkte

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Zeiterfassung API läuft'})

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Alle Mitarbeiter abrufen"""
    conn = get_db_connection()
    employees = conn.execute('SELECT * FROM employees ORDER BY name').fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in employees])

@app.route('/api/employees', methods=['POST'])
def create_employee():
    """Neuen Mitarbeiter erstellen"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()


    cursor.execute(
        'INSERT INTO employees (name, contract_hours, has_commission, start_date, end_date) VALUES (?, ?, ?, ?, ?)',
        (
            data['name'],
            data['contract_hours'],
            data.get('has_commission', False),
            data.get('start_date', date.today().isoformat()),
            data.get('end_date')
        )
    )
    employee_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': employee_id, 'message': 'Mitarbeiter erstellt'})

@app.route('/api/employees/<int:employee_id>', methods=['PUT'])
def update_employee(employee_id):
    """Mitarbeiter aktualisieren"""
    data = request.json
    
    conn = get_db_connection()
    conn.execute(
        'UPDATE employees SET name = ?, contract_hours = ?, has_commission = ?, is_active = ?, start_date = ?, end_date = ? WHERE id = ?',
        (
            data['name'],
            data['contract_hours'],
            data.get('has_commission', False),
            data.get('is_active', True),
            data.get('start_date'),
            data.get('end_date'),
            employee_id,
        )
    )
    conn.commit()
    conn.close()
    
    return jsonify({'message': 'Mitarbeiter aktualisiert'})

@app.route('/api/time-entries', methods=['GET'])
def get_time_entries():
    """Zeiterfassungen abrufen"""
    employee_id = request.args.get('employee_id')
    month = request.args.get('month')
    year = request.args.get('year')
    
    query = '''
        SELECT te.*, e.name as employee_name 
        FROM time_entries te 
        JOIN employees e ON te.employee_id = e.id
        WHERE 1=1
    '''
    params = []
    
    if employee_id:
        query += ' AND te.employee_id = ?'
        params.append(employee_id)
    
    if month and year:
        query += ' AND strftime("%m", te.date) = ? AND strftime("%Y", te.date) = ?'
        params.append(f"{int(month):02d}")
        params.append(year)
    
    query += ' ORDER BY te.date DESC'
    
    conn = get_db_connection()
    entries = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in entries])

@app.route('/api/time-entries', methods=['POST'])
def create_time_entry():
    """Neue Zeiterfassung erstellen"""
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    employee = cursor.execute(
        'SELECT start_date, end_date FROM employees WHERE id = ?',
        (data['employee_id'],)
    ).fetchone()
    if not employee:
        conn.close()
        return jsonify({'error': 'Mitarbeiter nicht gefunden'}), 404

    entry_date = datetime.strptime(data['date'], '%Y-%m-%d').date()

    # Beschäftigungszeitraum prüfen
    start = datetime.strptime(employee['start_date'], '%Y-%m-%d').date() if employee['start_date'] else None
    end = datetime.strptime(employee['end_date'], '%Y-%m-%d').date() if employee['end_date'] else None

    if (start and entry_date < start) or (end and entry_date > end):
        conn.close()
        if start and end:
            period = f"{start.isoformat()} bis {end.isoformat()}"
        elif start:
            period = f"ab {start.isoformat()}"
        else:
            period = f"bis {end.isoformat()}"
        return jsonify({'error': f'Datum außerhalb des Beschäftigungszeitraums ({period})'}), 400
    
    # Prüfe ob bereits Eintrag für diesen Tag existiert
    existing = cursor.execute(
        'SELECT id FROM time_entries WHERE employee_id = ? AND date = ?',
        (data['employee_id'], data['date'])
    ).fetchone()
    
    if existing:
        # Update existierenden Eintrag
        cursor.execute('''
            UPDATE time_entries SET 
                entry_type = ?, start_time = ?, end_time = ?, pause_minutes = ?,
                commission = ?, duftreise_bis_18 = ?, duftreise_ab_18 = ?, notes = ?
            WHERE id = ?
        ''', (
            data.get('entry_type', 'work'),
            data.get('start_time'),
            data.get('end_time'),
            data.get('pause_minutes', 0),
            data.get('commission', 0.0),
            data.get('duftreise_bis_18', 0),
            data.get('duftreise_ab_18', 0),
            data.get('notes', ''),
            existing['id']
        ))
        entry_id = existing['id']
    else:
        # Neuen Eintrag erstellen
        cursor.execute('''
            INSERT INTO time_entries 
            (employee_id, date, entry_type, start_time, end_time, pause_minutes,
             commission, duftreise_bis_18, duftreise_ab_18, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['employee_id'],
            data['date'],
            data.get('entry_type', 'work'),
            data.get('start_time'),
            data.get('end_time'),
            data.get('pause_minutes', 0),
            data.get('commission', 0.0),
            data.get('duftreise_bis_18', 0),
            data.get('duftreise_ab_18', 0),
            data.get('notes', '')
        ))
        entry_id = cursor.lastrowid
    
    conn.commit()
    conn.close()

    # Provision neu berechnen
    compute_commission_for_date(data['date'])

    return jsonify({'id': entry_id, 'message': 'Zeiterfassung gespeichert'})

@app.route('/api/time-entries/<int:entry_id>', methods=['PUT'])
def update_time_entry(entry_id):
    """Zeiterfassung aktualisieren"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Prüfe ob Eintrag existiert
    existing = cursor.execute('SELECT * FROM time_entries WHERE id = ?', (entry_id,)).fetchone()
    
    if not existing:
        conn.close()
        return jsonify({'error': 'Zeiterfassung nicht gefunden'}), 404

    employee = cursor.execute(
        'SELECT start_date, end_date FROM employees WHERE id = ?',
        (existing['employee_id'],)
    ).fetchone()
    entry_date = datetime.strptime(data.get('date', existing['date']), '%Y-%m-%d').date()

    # Beschäftigungszeitraum prüfen
    start = datetime.strptime(employee['start_date'], '%Y-%m-%d').date() if employee['start_date'] else None
    end = datetime.strptime(employee['end_date'], '%Y-%m-%d').date() if employee['end_date'] else None

    if (start and entry_date < start) or (end and entry_date > end):
        conn.close()
        if start and end:
            period = f"{start.isoformat()} bis {end.isoformat()}"
        elif start:
            period = f"ab {start.isoformat()}"
        else:
            period = f"bis {end.isoformat()}"
        return jsonify({'error': f'Datum außerhalb des Beschäftigungszeitraums ({period})'}), 400
    
    # Update Eintrag
    cursor.execute('''
        UPDATE time_entries SET 
            entry_type = ?, start_time = ?, end_time = ?, pause_minutes = ?,
            commission = ?, duftreise_bis_18 = ?, duftreise_ab_18 = ?, notes = ?
        WHERE id = ?
    ''', (
        data.get('entry_type', 'work'),
        data.get('start_time'),
        data.get('end_time'),
        data.get('pause_minutes', 0),
        data.get('commission', 0.0),
        data.get('duftreise_bis_18', 0),
        data.get('duftreise_ab_18', 0),
        data.get('notes', ''),
        entry_id
    ))
    
    conn.commit()
    conn.close()

    # Provision neu berechnen
    compute_commission_for_date(entry_date.isoformat())

    return jsonify({'message': 'Zeiterfassung aktualisiert'})


@app.route('/api/time-entries/<int:entry_id>', methods=['DELETE'])
def delete_time_entry(entry_id):
    """Zeiterfassung löschen"""
    conn = get_db_connection()
    cursor = conn.cursor()

    entry = cursor.execute('SELECT date FROM time_entries WHERE id = ?', (entry_id,)).fetchone()

    if not entry:
        conn.close()
        return jsonify({'error': 'Zeiterfassung nicht gefunden'}), 404

    entry_date = entry['date']

    cursor.execute('DELETE FROM time_entries WHERE id = ?', (entry_id,))

    conn.commit()
    conn.close()

    compute_commission_for_date(entry_date)

    return jsonify({'message': 'Zeiterfassung gelöscht'})


@app.route('/api/revenue', methods=['GET'])
def get_revenue():
    """Umsätze abrufen"""
    month = request.args.get('month')
    year = request.args.get('year')
    
    query = 'SELECT * FROM revenue WHERE 1=1'
    params = []
    
    if month and year:
        query += ' AND strftime("%m", date) = ? AND strftime("%Y", date) = ?'
        params.append(f"{int(month):02d}")
        params.append(year)
    
    query += ' ORDER BY date DESC'
    
    conn = get_db_connection()
    revenue = conn.execute(query, params).fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in revenue])

@app.route('/api/revenue', methods=['POST'])
def create_revenue():
    """Umsatz für ein Datum erstellen oder aktualisieren"""
    data = request.json

    conn = get_db_connection()
    cursor = conn.cursor()

    # Prüfen, ob für das Datum bereits ein Umsatz existiert
    existing = cursor.execute(
        'SELECT id FROM revenue WHERE date = ?',
        (data['date'],)
    ).fetchone()

    if existing:
        cursor.execute(
            'UPDATE revenue SET amount = ?, notes = ? WHERE id = ?',
            (data['amount'], data.get('notes', ''), existing['id'])
        )
        revenue_id = existing['id']
    else:
        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            (data['date'], data['amount'], data.get('notes', ''))
        )
        revenue_id = cursor.lastrowid

    conn.commit()
    conn.close()

    # Provision für diesen Tag neu berechnen
    compute_commission_for_date(data['date'])

    return jsonify({'id': revenue_id, 'message': 'Umsatz gespeichert'})


@app.route('/api/commission-settings', methods=['GET', 'POST'])
def commission_settings():
    """Provisionseinstellungen lesen oder speichern"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'GET':
        row = cursor.execute('SELECT percentage, monthly_max FROM commission_settings WHERE id = 1').fetchone()
        conn.close()
        if row:
            return jsonify({'percentage': row['percentage'], 'monthly_max': row['monthly_max']})
        return jsonify({'percentage': 0, 'monthly_max': 0})

    data = request.json
    cursor.execute('''
        INSERT INTO commission_settings (id, percentage, monthly_max)
        VALUES (1, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            percentage = excluded.percentage,
            monthly_max = excluded.monthly_max
    ''', (data.get('percentage', 0), data.get('monthly_max', 0)))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Einstellungen gespeichert'})


@app.route('/api/commission-thresholds', methods=['GET', 'POST'])
def commission_thresholds():
    """Provisionsschwellen abrufen oder speichern"""
    conn = get_db_connection()
    cursor = conn.cursor()
    if request.method == 'GET':
        rows = cursor.execute(
            'SELECT weekday, employee_count, threshold, valid_from '
            'FROM commission_thresholds '
            'ORDER BY weekday, employee_count, valid_from DESC'
        ).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows])

    data = request.json
    cursor.execute('''
        INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(weekday, employee_count, valid_from) DO UPDATE SET
            threshold = excluded.threshold
    ''', (
        data['weekday'],
        data['employee_count'],
        data.get('threshold', 0),
        data.get('valid_from', '1970-01-01'),
    ))
    conn.commit()
    conn.close()
    return jsonify({'message': 'Schwelle gespeichert'})

@app.route('/api/reports/monthly/<int:employee_id>/<int:year>/<int:month>')
def monthly_report(employee_id, year, month):
    """Monatsbericht für Mitarbeiter"""
    conn = get_db_connection()
    
    # Mitarbeiter-Info
    employee = conn.execute('SELECT * FROM employees WHERE id = ?', (employee_id,)).fetchone()
    
    # Zeiterfassungen des Monats
    entries = conn.execute('''
        SELECT * FROM time_entries
        WHERE employee_id = ? AND strftime("%Y", date) = ? AND strftime("%m", date) = ?
        ORDER BY date
    ''', (employee_id, str(year), f"{month:02d}")).fetchall()

    # Provisionen für alle Tage neu berechnen
    for entry in entries:
        compute_commission_for_date(entry['date'])

    conn.close()

    # Einträge nach Berechnung erneut laden
    conn = get_db_connection()
    entries = conn.execute('''
        SELECT * FROM time_entries
        WHERE employee_id = ? AND strftime("%Y", date) = ? AND strftime("%m", date) = ?
        ORDER BY date
    ''', (employee_id, str(year), f"{month:02d}")).fetchall()
    conn.close()
    
    if not employee:
        return jsonify({'error': 'Mitarbeiter nicht gefunden'}), 404
    
    # Berechnungen
    total_hours = 0
    total_commission = 0
    work_days = 0
    vacation_days = 0
    sick_days = 0
    total_duftreise_bis_18 = 0
    total_duftreise_ab_18 = 0
    
    for entry in entries:
        if entry['entry_type'] == 'work' and entry['start_time'] and entry['end_time']:
            # Stunden berechnen
            start = datetime.strptime(entry['start_time'], '%H:%M')
            end = datetime.strptime(entry['end_time'], '%H:%M')
            hours = (end - start).seconds / 3600 - (entry['pause_minutes'] or 0) / 60
            total_hours += hours
            work_days += 1
        elif entry['entry_type'] == 'vacation':
            vacation_days += 1
        elif entry['entry_type'] == 'sick':
            sick_days += 1
        
        total_commission += entry['commission'] or 0
        total_duftreise_bis_18 += entry['duftreise_bis_18'] or 0
        total_duftreise_ab_18 += entry['duftreise_ab_18'] or 0
    
    report = {
        'employee': dict(employee),
        'month': month,
        'year': year,
        'entries': [dict(row) for row in entries],
        'summary': {
            'total_hours': round(total_hours, 2),
            'total_commission': round(total_commission, 2),
            'work_days': work_days,
            'vacation_days': vacation_days,
            'sick_days': sick_days,
            'total_duftreise_bis_18': total_duftreise_bis_18,
            'total_duftreise_ab_18': total_duftreise_ab_18,
            'contract_hours_month': employee['contract_hours'] * 4.33  # Durchschnittliche Wochen pro Monat
        }
    }
    
    return jsonify(report)

# Statische Dateien servieren
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # Datenbank initialisieren
    init_database()
    
    # Server starten
    print("Starte Zeiterfassung Server...")
    port = int(os.environ.get("PORT", 5001))
    print(f"Öffne http://localhost:{port} in deinem Browser")
    debug_mode = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

