import sqlite3
import os
from datetime import datetime, timezone, timedelta
from sheets_helper import read_all, append_row, delete_row_by_match

DB_PATH = os.environ.get('DB_PATH', '/tmp/teaching_tools.db')
TAIWAN_TZ = timezone(timedelta(hours=8))
EQUIPMENT_SHEET = '器材'


class Database:
    def __init__(self):
        self._init()

    def _conn(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    week TEXT NOT NULL,
                    tools TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    created_at TEXT DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS states (
                    user_id TEXT PRIMARY KEY,
                    state TEXT,
                    temp_week TEXT,
                    temp_tools TEXT
                );
                CREATE TABLE IF NOT EXISTS tokens (
                    token TEXT PRIMARY KEY,
                    filepath TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );
            ''')

    def get_state(self, user_id):
        with self._conn() as c:
            row = c.execute('SELECT state FROM states WHERE user_id=?', (user_id,)).fetchone()
            return row['state'] if row else None

    def set_state(self, user_id, state, temp_week, temp_tools):
        with self._conn() as c:
            c.execute(
                'INSERT OR REPLACE INTO states VALUES (?,?,?,?)',
                (user_id, state, temp_week, temp_tools)
            )

    def get_temp_week(self, user_id):
        with self._conn() as c:
            row = c.execute('SELECT temp_week FROM states WHERE user_id=?', (user_id,)).fetchone()
            return row['temp_week'] if row else None

    def get_temp_data(self, user_id):
        with self._conn() as c:
            row = c.execute('SELECT temp_week, temp_tools FROM states WHERE user_id=?', (user_id,)).fetchone()
            return (row['temp_week'], row['temp_tools']) if row else (None, None)

    def clear_state(self, user_id):
        with self._conn() as c:
            c.execute('DELETE FROM states WHERE user_id=?', (user_id,))

    def save_record(self, user_id, week, tools, notes):
        append_row(EQUIPMENT_SHEET, {
            '日期': datetime.now(TAIWAN_TZ).strftime('%Y/%m/%d %H:%M'),
            '週次': week,
            '教具': tools,
            '備註': notes or '',
            'UserID': user_id,
        })

    def _user_rows(self, user_id):
        rows = read_all(EQUIPMENT_SHEET)
        return [r for r in rows if (r.get('UserID') or '').strip() == user_id]

    def get_all_records(self, user_id):
        return [{
            'week': r.get('週次', ''),
            'tools': r.get('教具', ''),
            'notes': r.get('備註', ''),
            'created_at': r.get('日期', ''),
        } for r in self._user_rows(user_id)]

    def get_recent(self, user_id, limit=5):
        all_rows = self.get_all_records(user_id)
        return all_rows[-limit:]

    def search_by_week(self, user_id, keyword):
        return [r for r in self.get_all_records(user_id)
                if keyword in r['week']]

    def delete_last(self, user_id):
        user_rows = self._user_rows(user_id)
        if not user_rows:
            return None
        last = user_rows[-1]
        date_val = last.get('日期', '')
        ok = delete_row_by_match(EQUIPMENT_SHEET, '日期', date_val)
        if ok:
            return f'{last.get("週次", "")} - {last.get("教具", "")}'
        return None

    def set_delete_refs(self, user_id, refs_json):
        with self._conn() as c:
            c.execute(
                'INSERT OR REPLACE INTO states VALUES (?,?,?,?)',
                (user_id, 'waiting_delete', refs_json, None)
            )

    def get_delete_refs(self, user_id):
        with self._conn() as c:
            row = c.execute('SELECT temp_week FROM states WHERE user_id=?', (user_id,)).fetchone()
            return row['temp_week'] if row else None

    def save_token(self, token, filepath):
        with self._conn() as c:
            c.execute('INSERT OR REPLACE INTO tokens VALUES (?,?,datetime("now"))', (token, filepath))

    def get_token(self, token):
        with self._conn() as c:
            row = c.execute('SELECT filepath, created_at FROM tokens WHERE token=?', (token,)).fetchone()
            if row:
                created_at = datetime.fromisoformat(row['created_at']).replace(tzinfo=timezone.utc)
                return row['filepath'], created_at
            return None, None
