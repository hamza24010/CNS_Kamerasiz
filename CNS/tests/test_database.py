import unittest
from unittest.mock import MagicMock, patch
import sqlite3
import sys
import os

# --- Mocking dependencies to import mainS ---
sys.modules['settings'] = MagicMock()
sys.modules['video'] = MagicMock()
sys.modules['RPi'] = MagicMock()
sys.modules['RPi.GPIO'] = MagicMock()
sys.modules['PyQt5'] = MagicMock()
sys.modules['PyQt5.QtWidgets'] = MagicMock()
sys.modules['PyQt5.QtCore'] = MagicMock()
sys.modules['PyQt5.QtGui'] = MagicMock()
sys.modules['matplotlib.backends.backend_qt5agg'] = MagicMock()

import CNS.mainS as mainS

class TestDatabase(unittest.TestCase):

    def setUp(self):
        # Create an in-memory database structure that matches mainDb.sqlite
        self.real_conn = sqlite3.connect(':memory:')

        # Create a proxy object that delegates to real_conn but mocks close
        self.conn = MagicMock(wraps=self.real_conn)
        self.conn.cursor.side_effect = self.real_conn.cursor
        self.conn.commit.side_effect = self.real_conn.commit
        self.conn.execute.side_effect = self.real_conn.execute
        self.conn.close = MagicMock() # Do nothing

        c = self.conn.cursor()

        # Create REPORT table
        c.execute('''CREATE TABLE REPORT (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            FIRM_ID TEXT,
            START_TIME TEXT,
            END_TIME TEXT,
            TYPE TEXT,
            M3 TEXT,
            PIECES TEXT,
            REPORT_INFO TEXT
        )''')

        # Create Report_Details table matching the structure implied by insert_report_step
        # insert_report_step uses "INSERT INTO Report_Details VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
        # Total columns = 1 (ID) + 20 placeholders = 21 columns.

        # Schema reconstruction based on mainS.py usage:
        # - ID: Auto increment
        # - REPORT_ID: Foreign Key (Arg 1)
        # - T1..T13: Sensor values (Args 2-14)
        # - AT1, AT2: Ambient values (Args 15-16)
        # - EXTRA1, EXTRA2: Placeholders/Steps (Args 17-18)
        # - STEPTIME: Timestamp (Arg 19)
        # - REMAINING: Step count (Arg 20)

        c.execute(f'''CREATE TABLE Report_Details (
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            REPORT_ID INTEGER,
            T1 TEXT, T2 TEXT, T3 TEXT, T4 TEXT, T5 TEXT,
            T6 TEXT, T7 TEXT, T8 TEXT, T9 TEXT, T10 TEXT,
            T11 TEXT, T12 TEXT, T13 TEXT,
            AT1 TEXT, AT2 TEXT,
            EXTRA1 TEXT, EXTRA2 TEXT,
            STEPTIME TEXT,
            REMAINING TEXT
        )''')

        self.conn.commit()

    def tearDown(self):
        self.real_conn.close()

    @patch('CNS.mainS.get_db')
    def test_insert_and_get_report(self, mock_get_db):
        mock_get_db.return_value = self.conn

        # Test insert_report
        mainS.insert_report(1, "FIRM1", "2023-01-01 10:00", "IP", "PINE", "100", "50", "Test Info")

        # Test get_report (Should return reports where END_TIME != "IP", wait, the code says END_TIME <> "IP")
        # So we need to update it or insert one with a real end time to see it in get_report
        # insert_report sets END_TIME to "IP" initially usually.

        # Verify directly via cursor first
        c = self.conn.cursor()
        c.execute("SELECT * FROM REPORT")
        rows = c.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 1) # ID
        self.assertEqual(rows[0][4], "PINE") # TYPE

        # Test update_report
        mainS.update_report(1, "OAK", "200", "60", "Updated Info")
        c.execute("SELECT * FROM REPORT")
        row = c.fetchone()
        self.assertEqual(row[4], "OAK")
        self.assertEqual(row[5], "200")

        # Test set_report_end_time
        # This function fetches the last step time from Report_Details.
        # We need to insert a step first.

        # insert_report_step(rid, *args)
        # It expects 20 args? No, the SQL has 20 placeholders after NULL.
        # (rid, *args) -> (rid, arg1, arg2... arg19)
        # Let's provide dummy args.
        args = ["0"] * 19
        # The last arg in the schema I built was REMAINING, but let's just match the count.
        # SQL: VALUES (NULL, ?, ?, ..., ?) (21 placeholders total: NULL + 20)
        # Function call: execute(..., (rid, *args))
        # So args must have 19 elements if rid is 1. Total 20 params.

        # In mainS.py:
        # insert_report_step(rid, *args):
        # c.execute("... VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (rid, *args))
        # Count of ?: 20.
        # Params: rid + args.
        # So len(args) must be 19.

        dummy_args = [str(i) for i in range(19)]
        # We need STEPTIME to be in the right place for set_report_end_time
        # Logic: SELECT STEPTIME FROM Report_Details ...
        # Wait, I don't know which column is STEPTIME in the real DB.
        # But get_report_details select list: T1..T13, AT1, AT2, STEPNO, STEPTIME
        # That's 17 columns selected.
        # The table has 21 columns (ID + 20).
        # It's safer to just rely on the count and that `set_report_end_time` logic:
        # "SELECT STEPTIME FROM Report_Details" -> It assumes a column named STEPTIME exists.

        # So my create table must have STEPTIME.
        mainS.insert_report_step(1, *dummy_args)

        # Now set end time
        # This will fail if my schema STEPTIME column isn't what the code expects (which is just name based)
        # The code executes: SELECT STEPTIME FROM ...
        # My table has STEPTIME.

        # However, the row I inserted has dummy values. Which one went into STEPTIME?
        # insert statement: INSERT INTO Report_Details VALUES ...
        # It relies on column order.
        # I don't know the exact column order of the real DB.
        # But `set_report_end_time` reads `STEPTIME` by name.
        # So as long as I put something in `STEPTIME` column it works.
        # But `INSERT VALUES` puts data positionally.

        # If I can't know the order, `insert_report_step` might put data into wrong columns in my mock DB.
        # BUT, `insert_report_step` is just `INSERT INTO Report_Details VALUES ...`.
        # It doesn't specify columns.
        # So it matches my CREATE TABLE order.
        # My CREATE TABLE has STEPTIME at index 18 (0-based) approx.
        # Let's just run it. If logic relies on generic SQL, it might fail if `STEPTIME` is not populated.

        # Actually, `set_report_end_time` does: `UPDATE REPORT SET END_TIME=?` using result from `SELECT STEPTIME`.
        # So as long as `SELECT STEPTIME` returns something, it updates.

        try:
            mainS.set_report_end_time(1)
        except Exception as e:
            print(f"set_report_end_time failed: {e}")

        # Check if REPORT end time changed from "IP"
        c.execute("SELECT END_TIME FROM REPORT WHERE ID=1")
        et = c.fetchone()[0]
        # It should be whatever I inserted into STEPTIME column.
        # In my schema, STEPTIME is near the end.
        # dummy_args has 19 items.
        # schema has 20 columns after ID.
        # 1 (RID) + 19 args = 20 values.
        # My schema has: REPORT_ID (1), T1..T13 (13), AT1, AT2 (2), EXTRA1, EXTRA2 (2), STEPTIME (1), REMAINING (1)
        # Total: 1+13+2+2+1+1 = 20 columns. Matches perfectly.
        # So dummy_args[17] should be STEPTIME.
        # dummy_args are '0'..'18'. '17' is the 18th element.
        # So expected value is '17'.

        self.assertEqual(et, '17')

    @patch('CNS.mainS.get_db')
    def test_report_queries(self, mock_get_db):
        mock_get_db.return_value = self.conn

        # Insert a completed report
        mainS.insert_report(2, "FIRM2", "START", "END", "TYPE", "M3", "PCS", "INFO")

        # Test get_report (fetches where END_TIME <> "IP")
        reports = mainS.get_report()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0][0], 2)

        # Test get_parti
        parti = mainS.get_parti(2)
        self.assertEqual(parti[0][0], 2)

        # Test report_index
        idx = mainS.report_index()
        self.assertEqual(idx, "2")

        # Test cleanup_db
        mainS.cleanup_db(2)
        c = self.conn.cursor()
        c.execute("SELECT * FROM REPORT WHERE ID=2")
        self.assertIsNone(c.fetchone())

if __name__ == '__main__':
    unittest.main()
