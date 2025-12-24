import os
import tempfile
import unittest

import server


class CommissionThresholdsTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp_db = tempfile.NamedTemporaryFile(delete=False)
        self.tmp_db.close()
        server.DB_PATH = self.tmp_db.name
        if os.path.exists(server.DB_PATH):
            os.remove(server.DB_PATH)
        server.init_database()
        conn = server.get_db_connection()
        conn.execute(
            'UPDATE commission_settings SET percentage = 10, monthly_max = 10000 WHERE id = 1'
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.tmp_db.name):
            os.remove(self.tmp_db.name)

    def test_commission_thresholds_with_valid_from(self):
        conn = server.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM commission_thresholds')
        cursor.execute('DELETE FROM time_entries')
        cursor.execute('DELETE FROM revenue')
        cursor.execute('DELETE FROM employees')

        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Test Employee', 40, 1, 1, '2023-01-01'),
        )
        employee_id = cursor.lastrowid

        # Vorherige Arbeitstage, um die 160 Stunden bereits vor Juni zu erreichen
        for day in range(1, 17):
            cursor.execute(
                '''
                    INSERT INTO time_entries (
                        employee_id, date, entry_type, start_time, end_time, pause_minutes,
                        commission, duftreise_bis_18, duftreise_ab_18, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (employee_id, f'2023-05-{day:02d}', 'work', '08:00', '18:00', 0, 0, 0, 0, ''),
            )

        cursor.execute(
            '''
                INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
                VALUES (?, ?, ?, ?)
            ''',
            (0, 1, 100, '2023-01-01'),
        )
        cursor.execute(
            '''
                INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
                VALUES (?, ?, ?, ?)
            ''',
            (0, 1, 200, '2024-01-01'),
        )

        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (employee_id, '2023-06-05', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )
        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            ('2023-06-05', 150, ''),
        )

        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (employee_id, '2024-06-03', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )
        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            ('2024-06-03', 150, ''),
        )

        conn.commit()
        conn.close()

        server.compute_commission_for_date('2023-06-05')
        server.compute_commission_for_date('2024-06-03')

        conn = server.get_db_connection()
        cursor = conn.cursor()
        commission_old = cursor.execute(
            'SELECT commission FROM time_entries WHERE date = ?',
            ('2023-06-05',),
        ).fetchone()[0]
        commission_new = cursor.execute(
            'SELECT commission FROM time_entries WHERE date = ?',
            ('2024-06-03',),
        ).fetchone()[0]
        conn.close()

        self.assertEqual(commission_old, 15.0)
        self.assertEqual(commission_new, 0)

    def test_threshold_counts_only_commission_eligible_employees(self):
        conn = server.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM commission_thresholds')
        cursor.execute('DELETE FROM time_entries')
        cursor.execute('DELETE FROM revenue')
        cursor.execute('DELETE FROM employees')

        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Eligible Employee', 40, 1, 1, '2023-01-01'),
        )
        eligible_id = cursor.lastrowid

        # Vorarbeit, um die 160-Stunden-Schwelle zu erreichen
        for day in range(1, 17):
            cursor.execute(
                '''
                    INSERT INTO time_entries (
                        employee_id, date, entry_type, start_time, end_time, pause_minutes,
                        commission, duftreise_bis_18, duftreise_ab_18, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (eligible_id, f'2024-05-{day:02d}', 'work', '08:00', '18:00', 0, 0, 0, 0, ''),
            )

        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Ineligible Employee', 40, 0, 1, '2023-01-01'),
        )
        ineligible_id = cursor.lastrowid

        cursor.execute(
            '''
                INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
                VALUES (?, ?, ?, ?)
            ''',
            (0, 1, 100, '2023-01-01'),
        )
        cursor.execute(
            '''
                INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
                VALUES (?, ?, ?, ?)
            ''',
            (0, 2, 200, '2023-01-01'),
        )

        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (eligible_id, '2024-06-03', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )
        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (ineligible_id, '2024-06-03', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )

        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            ('2024-06-03', 150, ''),
        )

        conn.commit()
        conn.close()

        server.compute_commission_for_date('2024-06-03')

        conn = server.get_db_connection()
        cursor = conn.cursor()
        commission = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (eligible_id, '2024-06-03'),
        ).fetchone()[0]
        conn.close()

        self.assertGreater(commission, 0)


    def test_commission_requires_160_hours_across_months(self):
        conn = server.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM commission_thresholds')
        cursor.execute('DELETE FROM time_entries')
        cursor.execute('DELETE FROM revenue')
        cursor.execute('DELETE FROM employees')

        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Commission Employee', 40, 1, 1, '2024-01-01'),
        )
        employee_id = cursor.lastrowid

        # 15 Tage im Januar zu je 10 Stunden (insgesamt 150 Stunden)
        january_days = [f'2024-01-{day:02d}' for day in range(1, 16)]
        for day in january_days:
            cursor.execute(
                '''
                    INSERT INTO time_entries (
                        employee_id, date, entry_type, start_time, end_time, pause_minutes,
                        commission, duftreise_bis_18, duftreise_ab_18, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (employee_id, day, 'work', '08:00', '18:00', 0, 0, 0, 0, ''),
            )
            cursor.execute(
                'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
                (day, 200, ''),
            )

        # Am 1. Februar werden die 160 Stunden erreicht
        february_day = '2024-02-01'
        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (employee_id, february_day, 'work', '08:00', '18:00', 0, 0, 0, 0, ''),
        )
        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            (february_day, 200, ''),
        )

        conn.commit()
        conn.close()

        for day in january_days + [february_day]:
            server.compute_commission_for_date(day)

        conn = server.get_db_connection()
        cursor = conn.cursor()
        january_commission = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (employee_id, '2024-01-15'),
        ).fetchone()[0]
        february_commission = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (employee_id, february_day),
        ).fetchone()[0]
        conn.close()

        self.assertEqual(january_commission, 0)
        self.assertGreater(february_commission, 0)

    def test_no_commission_when_threshold_missing_for_employee_count(self):
        conn = server.get_db_connection()
        cursor = conn.cursor()

        cursor.execute('DELETE FROM commission_thresholds')
        cursor.execute('DELETE FROM time_entries')
        cursor.execute('DELETE FROM revenue')
        cursor.execute('DELETE FROM employees')

        # Nur eine Schwelle für einen Mitarbeiter hinterlegen
        cursor.execute(
            '''
                INSERT INTO commission_thresholds (weekday, employee_count, threshold, valid_from)
                VALUES (?, ?, ?, ?)
            ''',
            (0, 1, 200, '2024-01-01'),
        )

        # Erster Mitarbeiter mit Provision
        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Erster', 40, 1, 1, '2024-01-01'),
        )
        first_employee = cursor.lastrowid

        # Zweiter Mitarbeiter trägt sich erst später ein
        cursor.execute(
            '''
                INSERT INTO employees (
                    name, contract_hours, has_commission, is_active, start_date
                ) VALUES (?, ?, ?, ?, ?)
            ''',
            ('Nachtrag', 40, 1, 1, '2024-01-01'),
        )
        second_employee = cursor.lastrowid

        # Umsatz unterhalb der Schwelle für einen Mitarbeiter
        cursor.execute(
            'INSERT INTO revenue (date, amount, notes) VALUES (?, ?, ?)',
            ('2024-06-03', 150, ''),
        )

        # Erster Mitarbeitereintrag (bereits keine Provision wegen Schwellwert)
        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (first_employee, '2024-06-03', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )

        conn.commit()
        conn.close()

        # Initial keine Provision
        server.compute_commission_for_date('2024-06-03')

        conn = server.get_db_connection()
        cursor = conn.cursor()
        first_commission = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (first_employee, '2024-06-03'),
        ).fetchone()[0]
        conn.close()

        self.assertEqual(first_commission, 0)

        # Zweiter Mitarbeiter trägt sich nachträglich ein
        conn = server.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''
                INSERT INTO time_entries (
                    employee_id, date, entry_type, start_time, end_time, pause_minutes,
                    commission, duftreise_bis_18, duftreise_ab_18, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (second_employee, '2024-06-03', 'work', '09:00', '17:00', 60, 0, 0, 0, ''),
        )
        conn.commit()
        conn.close()

        # Trotz fehlender Schwelle für zwei Mitarbeitende keine Provision
        server.compute_commission_for_date('2024-06-03')

        conn = server.get_db_connection()
        cursor = conn.cursor()
        first_commission_after = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (first_employee, '2024-06-03'),
        ).fetchone()[0]
        second_commission_after = cursor.execute(
            'SELECT commission FROM time_entries WHERE employee_id = ? AND date = ?',
            (second_employee, '2024-06-03'),
        ).fetchone()[0]
        conn.close()

        self.assertEqual(first_commission_after, 0)
        self.assertEqual(second_commission_after, 0)


if __name__ == '__main__':
    unittest.main()
