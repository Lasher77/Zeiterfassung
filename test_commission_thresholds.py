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

    def test_threshold_counts_all_employees(self):
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

        self.assertEqual(commission, 0)


if __name__ == '__main__':
    unittest.main()
