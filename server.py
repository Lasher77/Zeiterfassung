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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
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
    
    # Beispieldaten einfügen falls Tabelle leer
    cursor.execute('SELECT COUNT(*) FROM employees')
    if cursor.fetchone()[0] == 0:
        employees = [
            ("Alina W.", 20, 0, 1),
            ("Valeria Z.", 25, 1, 1),
            ("Eva C.", 30, 1, 1),
            ("Hannah S.", 20, 0, 1),
            ("Hans K.", 40, 1, 1),
            ("Lena K.", 25, 1, 1),
            ("Lorena M.", 30, 1, 1),
            ("Lilo Ming K.", 20, 0, 1)
        ]
        cursor.executemany(
            'INSERT INTO employees (name, contract_hours, has_commission, is_active) VALUES (?, ?, ?, ?)',
            employees
        )
    
    conn.commit()
    conn.close()
    print("Datenbank initialisiert!")

def get_db_connection():
    """Erstelle Datenbankverbindung"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Ermöglicht dict-ähnlichen Zugriff
    return conn

# API Endpunkte

@app.route('/api/health')
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'message': 'Zeiterfassung API läuft'})

@app.route('/api/employees', methods=['GET'])
def get_employees():
    """Alle Mitarbeiter abrufen"""
    conn = get_db_connection()
    employees = conn.execute('SELECT * FROM employees WHERE is_active = 1 ORDER BY name').fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in employees])

@app.route('/api/employees', methods=['POST'])
def create_employee():
    """Neuen Mitarbeiter erstellen"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO employees (name, contract_hours, has_commission) VALUES (?, ?, ?)',
        (data['name'], data['contract_hours'], data.get('has_commission', False))
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
        'UPDATE employees SET name = ?, contract_hours = ?, has_commission = ?, is_active = ? WHERE id = ?',
        (data['name'], data['contract_hours'], data.get('has_commission', False), 
         data.get('is_active', True), employee_id)
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
    
    return jsonify({'id': entry_id, 'message': 'Zeiterfassung gespeichert'})

@app.route('/api/time-entries/<int:entry_id>', methods=['PUT'])
def update_time_entry(entry_id):
    """Zeiterfassung aktualisieren"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Prüfe ob Eintrag existiert
    existing = cursor.execute('SELECT id FROM time_entries WHERE id = ?', (entry_id,)).fetchone()
    
    if not existing:
        conn.close()
        return jsonify({'error': 'Zeiterfassung nicht gefunden'}), 404
    
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
    
    return jsonify({'message': 'Zeiterfassung aktualisiert'})

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
    """Neuen Umsatz erstellen"""
    data = request.json
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
        (data['date'], data['amount'], data.get('notes', ''))
    )
    revenue_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({'id': revenue_id, 'message': 'Umsatz gespeichert'})

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
    app.run(host='0.0.0.0', port=port, debug=True)

