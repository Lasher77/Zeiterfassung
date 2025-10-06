#!/usr/bin/env python3
"""
Arbeitszeiterfassung Backend mit SQLite
"""

import logging
import sqlite3
import json
import csv
import io
import os
from datetime import datetime, date
from xml.sax.saxutils import escape

from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Table,
    TableStyle,
    Spacer,
)
if not logging.getLogger().handlers:
    logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
CORS(app)  # Erlaube Cross-Origin Requests

logger = logging.getLogger(__name__)

# Datenbank-Pfad
DB_PATH = 'zeiterfassung.db'

MONTH_NAMES = [
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember'
]

ENTRY_TYPE_LABELS = {
    'work': 'Arbeit',
    'vacation': 'Urlaub',
    'sick': 'Krankheit'
}

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

    # Arbeitszeiten des Tages (für Schwellwert alle, für Auszahlung nur berechtigte)
    entries = cursor.execute(
        '''
            SELECT te.id, te.employee_id, te.start_time, te.end_time,
                   te.pause_minutes, e.has_commission
            FROM time_entries te
            JOIN employees e ON te.employee_id = e.id
            WHERE te.date = ?
              AND te.entry_type = 'work'
              AND te.start_time IS NOT NULL AND te.end_time IS NOT NULL
        ''',
        (date_str,),
    ).fetchall()

    emp_hours = {}
    entry_ids = {}
    all_employee_ids = set()
    for row in entries:
        start = datetime.strptime(row['start_time'], '%H:%M')
        end = datetime.strptime(row['end_time'], '%H:%M')
        hours = (end - start).seconds / 3600 - (row['pause_minutes'] or 0) / 60
        all_employee_ids.add(row['employee_id'])

        if row['has_commission']:
            emp_hours.setdefault(row['employee_id'], 0)
            emp_hours[row['employee_id']] += hours
            entry_ids[row['employee_id']] = row['id']

    employee_count = len(all_employee_ids)

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

def fetch_employee_month_entries(employee_id, year, month):
    """Lade Zeiteinträge eines Mitarbeiters für einen bestimmten Monat"""
    conn = get_db_connection()
    entries = conn.execute(
        '''
            SELECT * FROM time_entries
            WHERE employee_id = ?
              AND strftime("%Y", date) = ?
              AND strftime("%m", date) = ?
            ORDER BY date
        ''',
        (employee_id, str(year), f"{month:02d}"),
    ).fetchall()
    conn.close()
    return entries


def build_month_summary(entries, contract_hours=None):
    """Berechne Kennzahlen über eine Menge von Zeiteinträgen"""
    total_hours = 0
    total_commission = 0
    work_days = 0
    vacation_days = 0
    sick_days = 0
    total_duftreise_bis_18 = 0
    total_duftreise_ab_18 = 0

    for entry in entries:
        entry_type = entry['entry_type']
        if entry_type == 'work' and entry['start_time'] and entry['end_time']:
            start = datetime.strptime(entry['start_time'], '%H:%M')
            end = datetime.strptime(entry['end_time'], '%H:%M')
            hours = (end - start).seconds / 3600 - (entry['pause_minutes'] or 0) / 60
            total_hours += hours
            work_days += 1
        elif entry_type == 'vacation':
            vacation_days += 1
        elif entry_type == 'sick':
            sick_days += 1

        total_commission += entry['commission'] or 0
        total_duftreise_bis_18 += entry['duftreise_bis_18'] or 0
        total_duftreise_ab_18 += entry['duftreise_ab_18'] or 0

    summary = {
        'total_hours': round(total_hours, 2),
        'total_commission': round(total_commission, 2),
        'work_days': work_days,
        'vacation_days': vacation_days,
        'sick_days': sick_days,
        'total_duftreise_bis_18': total_duftreise_bis_18,
        'total_duftreise_ab_18': total_duftreise_ab_18,
    }

    if contract_hours is not None:
        summary['contract_hours_month'] = contract_hours * 4.33

    return summary


def get_month_overview(year, month):
    """Bereite Monatsübersicht für alle aktiven Mitarbeitenden auf"""
    conn = get_db_connection()
    employees = conn.execute(
        'SELECT * FROM employees WHERE is_active = 1 ORDER BY name'
    ).fetchall()
    conn.close()

    overview_employees = []

    for employee in employees:
        entries = fetch_employee_month_entries(employee['id'], year, month)

        for entry in entries:
            compute_commission_for_date(entry['date'])

        entries = fetch_employee_month_entries(employee['id'], year, month)
        summary = build_month_summary(entries, employee['contract_hours'])

        overview_employees.append({
            'employee': dict(employee),
            'entries': [dict(row) for row in entries],
            'summary': summary,
        })

    return {
        'month': month,
        'year': year,
        'employees': overview_employees,
    }


def _format_reports_overview_for_pdf(overview):
    """Bereite Daten für den PDF-Export auf."""
    formatted_employees = []

    for item in overview.get('employees', []):
        employee = item.get('employee', {})
        summary = item.get('summary', {})
        processed_entries = []

        for entry in item.get('entries', []):
            entry_data = dict(entry)
            date_str = entry_data.get('date')

            try:
                parsed_date = datetime.strptime(date_str, '%Y-%m-%d') if date_str else None
            except ValueError:
                parsed_date = None

            if parsed_date:
                entry_data['formatted_date'] = parsed_date.strftime('%d.%m.%Y')
            else:
                entry_data['formatted_date'] = date_str or ''

            entry_type = entry_data.get('entry_type')
            entry_data['entry_type_label'] = ENTRY_TYPE_LABELS.get(entry_type, entry_type or '')

            start_time = entry_data.get('start_time')
            end_time = entry_data.get('end_time')
            pause_minutes = entry_data.get('pause_minutes') or 0

            calculated_hours = None
            if entry_type == 'work' and start_time and end_time:
                try:
                    start_dt = datetime.strptime(start_time, '%H:%M')
                    end_dt = datetime.strptime(end_time, '%H:%M')
                    duration_hours = (end_dt - start_dt).total_seconds() / 3600
                    duration_hours -= (pause_minutes or 0) / 60
                    if duration_hours < 0:
                        duration_hours += 24
                    calculated_hours = round(duration_hours, 2)
                except ValueError:
                    calculated_hours = None

            entry_data['calculated_hours'] = calculated_hours
            entry_data['pause_minutes'] = pause_minutes
            commission_value = entry_data.get('commission')
            if commission_value is None:
                commission_value = 0
            entry_data['commission'] = round(float(commission_value), 2)
            entry_data['duftreise_bis_18'] = entry_data.get('duftreise_bis_18') or 0
            entry_data['duftreise_ab_18'] = entry_data.get('duftreise_ab_18') or 0
            entry_data['notes'] = entry_data.get('notes') or ''

            processed_entries.append(entry_data)

        formatted_employees.append({
            'employee': employee,
            'summary': summary,
            'entries': processed_entries,
        })

    overview['employees'] = formatted_employees
    return overview


def _render_reports_overview_pdf(
    prepared_overview, month_name, generated_at, include_details=False
):
    """Erzeuge ein PDF-Dokument der Monatsübersicht und liefere dessen Bytes."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Monatsübersicht {month_name} {prepared_overview.get('year', '')}",
    )

    styles = getSampleStyleSheet()
    if 'Small' not in styles:
        styles.add(
            ParagraphStyle(name='Small', parent=styles['Normal'], fontSize=9, leading=11)
        )
    if 'Italic' not in styles:
        styles.add(
            ParagraphStyle(name='Italic', parent=styles['Normal'], fontName='Helvetica-Oblique')
        )
    if 'Metric' not in styles:
        styles.add(
            ParagraphStyle(
                name='Metric',
                parent=styles['Normal'],
                leading=14,
                alignment=1,
                spaceBefore=0,
                spaceAfter=0,
            )
        )
    if 'EmployeeName' not in styles:
        styles.add(
            ParagraphStyle(
                name='EmployeeName',
                parent=styles['Normal'],
                fontSize=12,
                leading=14,
                spaceBefore=0,
                spaceAfter=0,
            )
        )

    story = []
    title_parts = ["Monatsübersicht", month_name, str(prepared_overview.get('year', ''))]
    title_text = " ".join(part for part in title_parts if part)
    story.append(Paragraph(title_text.strip(), styles['Title']))
    story.append(
        Paragraph(
            f"Generiert am {generated_at.strftime('%d.%m.%Y %H:%M')}",
            styles['Small'],
        )
    )
    story.append(Spacer(1, 12))

    def format_decimal(value, suffix=''):
        if value is None:
            return '-'
        try:
            number = float(value)
        except (TypeError, ValueError):
            return str(value)
        formatted = f"{number:.2f}" if not number.is_integer() else f"{int(number)}"
        return f"{formatted}{suffix}"

    def format_hours_minutes(value):
        if value is None:
            return '-'
        try:
            total_minutes = int(round(float(value) * 60))
        except (TypeError, ValueError):
            return str(value)

        hours = total_minutes // 60
        minutes = total_minutes % 60
        return f"{hours} h {minutes:02d} min"

    for item in prepared_overview.get('employees', []):
        employee = item.get('employee', {}) or {}
        summary = item.get('summary', {}) or {}
        entries = item.get('entries', []) or []
        employee_name = employee.get('name') or 'Unbekannter Mitarbeitender'
        safe_employee_name = escape(employee_name)
        name_paragraph = Paragraph(
            (
                "<para alignment='left'><font size='12'><b>{}</b></font><br/>"
                "<font size='9' color='#555555'>Monatsübersicht</font></para>"
            ).format(safe_employee_name),
            styles['EmployeeName'],
        )

        metrics_config = [
            ('Gesamtstunden', summary.get('total_hours'), ''),
            ('Arbeitstage', summary.get('work_days'), ''),
            ('Urlaubstage', summary.get('vacation_days'), ''),
            ('Krankheitstage', summary.get('sick_days'), ''),
            (
                'Duftreisen vor 18 Uhr',
                summary.get('total_duftreise_bis_18'),
                '',
            ),
            (
                'Duftreisen nach 18 Uhr',
                summary.get('total_duftreise_ab_18'),
                '',
            ),
            ('Provision gesamt', summary.get('total_commission'), ' €'),
        ]

        metric_cells = []
        for label, value, suffix in metrics_config:
            if label == 'Gesamtstunden':
                metric_value = format_hours_minutes(value)
            else:
                metric_value = format_decimal(value, suffix)
            metric_value = escape(metric_value)
            metric_label = escape(label)
            metric_cells.append(
                Paragraph(
                    "<para alignment='center'><font size='14'><b>{}</b></font><br/><font size='9' color='#555555'>{}</font></para>".format(
                        metric_value, metric_label
                    ),
                    styles['Metric'],
                )
            )

        available_width = doc.width
        name_col_width = available_width * 0.22
        if metric_cells:
            metric_col_width = (available_width - name_col_width) / len(metric_cells)
        else:
            metric_col_width = available_width - name_col_width

        summary_row = [name_paragraph] + metric_cells
        summary_table = Table(
            [summary_row],
            colWidths=[name_col_width] + [metric_col_width] * len(metric_cells),
            hAlign='LEFT',
        )
        summary_table.setStyle(
            TableStyle(
                [
                    ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#EEF2F7')),
                    ('BACKGROUND', (1, 0), (-1, 0), colors.HexColor('#F9FAFB')),
                    ('BOX', (0, 0), (-1, -1), 0.6, colors.HexColor('#D8DFEA')),
                    ('INNERGRID', (1, 0), (-1, -1), 0.4, colors.HexColor('#E5EAF2')),
                    ('LEFTPADDING', (0, 0), (-1, -1), 10),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 10),
                    ('TOPPADDING', (0, 0), (-1, -1), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
                ]
            )
        )
        story.append(summary_table)

        if include_details:
            story.append(Spacer(1, 8))

            if entries:
                detail_headers = [
                    'Datum',
                    'Typ',
                    'Start',
                    'Ende',
                    'Pause',
                    'Arbeitszeit',
                    'Duftreisen < 18',
                    'Duftreisen ≥ 18',
                    'Provision',
                    'Notizen',
                ]
                detail_rows = [
                    [Paragraph(f'<b>{escape(header)}</b>', styles['Small']) for header in detail_headers]
                ]

                for entry in entries:
                    pause_value = entry.get('pause_minutes')
                    if pause_value in (None, ''):
                        pause_display = '-'
                    else:
                        pause_display = f"{int(pause_value)} min"

                    detail_rows.append(
                        [
                            Paragraph(escape(entry.get('formatted_date') or '-'), styles['Small']),
                            Paragraph(escape(entry.get('entry_type_label') or '-'), styles['Small']),
                            Paragraph(escape(entry.get('start_time') or '-'), styles['Small']),
                            Paragraph(escape(entry.get('end_time') or '-'), styles['Small']),
                            Paragraph(escape(pause_display), styles['Small']),
                            Paragraph(
                                escape(format_hours_minutes(entry.get('calculated_hours'))),
                                styles['Small'],
                            ),
                            Paragraph(
                                escape(format_decimal(entry.get('duftreise_bis_18'))),
                                styles['Small'],
                            ),
                            Paragraph(
                                escape(format_decimal(entry.get('duftreise_ab_18'))),
                                styles['Small'],
                            ),
                            Paragraph(
                                escape(format_decimal(entry.get('commission'), ' €')),
                                styles['Small'],
                            ),
                            Paragraph(escape(entry.get('notes') or '-'), styles['Small']),
                        ]
                    )

                column_widths = [
                    doc.width * width
                    for width in [0.1, 0.12, 0.08, 0.08, 0.08, 0.1, 0.08, 0.08, 0.1, 0.18]
                ]

                detail_table = Table(detail_rows, colWidths=column_widths, repeatRows=1)
                detail_table.setStyle(
                    TableStyle(
                        [
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E3E8F0')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1F2937')),
                            ('BOX', (0, 0), (-1, -1), 0.4, colors.HexColor('#D1D5DB')),
                            ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#E5E7EB')),
                            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                            ('ALIGN', (2, 1), (8, -1), 'CENTER'),
                            ('LEFTPADDING', (0, 0), (-1, -1), 6),
                            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                            ('TOPPADDING', (0, 0), (-1, -1), 4),
                            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                story.append(detail_table)
            else:
                story.append(Paragraph('Keine Tagesdaten vorhanden.', styles['Small']))

        story.append(Spacer(1, 14))

    doc.build(story)
    return buffer.getvalue()


def _build_reports_overview_pdf_response(year, month, include_details=False):
    """Erzeuge eine HTTP-Antwort mit dem Monatsübersicht-PDF."""
    if month < 1 or month > 12:
        return jsonify({'error': 'Ungültiger Monat'}), 400

    overview = get_month_overview(year, month)
    prepared_overview = _format_reports_overview_for_pdf(overview.copy())

    try:
        month_name = MONTH_NAMES[month - 1]
    except IndexError:
        month_name = str(month)

    generated_at = datetime.now()
    try:
        pdf_bytes = _render_reports_overview_pdf(
            prepared_overview,
            month_name,
            generated_at,
            include_details=include_details,
        )
    except Exception as exc:
        logger.exception('PDF-Erstellung fehlgeschlagen')
        return jsonify({'error': f'PDF-Erstellung fehlgeschlagen: {exc}'}), 500

    filename_suffix = '_detailliert' if include_details else ''
    filename = f"auswertungen_{year}_{month:02d}{filename_suffix}.pdf"
    headers = {'Content-Disposition': f'attachment; filename="{filename}"'}

    return Response(pdf_bytes, mimetype='application/pdf', headers=headers)


@app.route('/api/reports/monthly/<int:employee_id>/<int:year>/<int:month>')
def monthly_report(employee_id, year, month):
    """Monatsbericht für Mitarbeiter"""
    conn = get_db_connection()
    
    # Mitarbeiter-Info
    employee = conn.execute('SELECT * FROM employees WHERE id = ?', (employee_id,)).fetchone()
    conn.close()

    entries = fetch_employee_month_entries(employee_id, year, month)

    for entry in entries:
        compute_commission_for_date(entry['date'])

    entries = fetch_employee_month_entries(employee_id, year, month)
    
    if not employee:
        return jsonify({'error': 'Mitarbeiter nicht gefunden'}), 404
    
    summary = build_month_summary(entries, employee['contract_hours'])

    report = {
        'employee': dict(employee),
        'month': month,
        'year': year,
        'entries': [dict(row) for row in entries],
        'summary': summary,
    }

    return jsonify(report)


@app.route('/api/reports/overview/<int:year>/<int:month>')
def reports_overview(year, month):
    """Monatliche Übersicht für alle aktiven Mitarbeitenden"""
    overview = get_month_overview(year, month)
    return jsonify(overview)


@app.route('/api/reports/overview/<int:year>/<int:month>/export')
def reports_overview_export(year, month):
    """Exportiere Monatsübersicht als CSV"""
    overview = get_month_overview(year, month)

    output = io.StringIO()
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        'Mitarbeiter',
        'Gesamtstunden',
        'Arbeitstage',
        'Urlaubstage',
        'Krankheitstage',
        'Duftreisen vor 18 Uhr',
        'Duftreisen nach 18 Uhr',
        'Provision',
        'Vertragliche Stunden (Monat)',
    ])

    for item in overview['employees']:
        employee = item['employee']
        summary = item['summary']
        writer.writerow([
            employee['name'],
            summary['total_hours'],
            summary['work_days'],
            summary['vacation_days'],
            summary['sick_days'],
            summary['total_duftreise_bis_18'],
            summary['total_duftreise_ab_18'],
            summary['total_commission'],
            summary.get('contract_hours_month', 0),
        ])

    output.seek(0)

    filename = f"auswertungen_{year}_{month:02d}.csv"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"'
    }

    return Response(output.getvalue(), mimetype='text/csv', headers=headers)


@app.route('/api/reports/overview/<int:year>/<int:month>/export/pdf')
def reports_overview_export_pdf(year, month):
    """Exportiere Monatsübersicht als PDF mithilfe von ReportLab."""
    return _build_reports_overview_pdf_response(year, month, include_details=False)


@app.route('/api/reports/overview/<int:year>/<int:month>/export/pdf/detailed')
def reports_overview_export_pdf_detailed(year, month):
    """Exportiere Monatsübersicht als detailliertes PDF mit Tagesübersicht."""
    return _build_reports_overview_pdf_response(year, month, include_details=True)

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

