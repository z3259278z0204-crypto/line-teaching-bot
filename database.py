import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.environ.get('DB_PATH', '/tmp/teaching_tools.db')


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
        with self._conn() as c:
            c.execute(
                'INSERT INTO records (user_id, week, tools, notes) VALUES (?,?,?,?)',
                (user_id, week, tools, notes)
            )

    def get_all_records(self, user_id):
        with self._conn() as c:
            rows = c.execute(
                'SELECT week, tools, notes, created_at FROM records WHERE user_id=? ORDER BY id ASC',
                (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_recent(self, user_id, limit=5):
        with self._conn() as c:
            rows = c.execute(
                'SELECT week, tools, notes, created_at FROM records WHERE user_id=? ORDER BY id DESC LIMIT ?',
                (user_id, limit)
            ).fetchall()
            return [dict(r) for r in reversed(rows)]

    def delete_last(self, user_id):
        with self._conn() as c:
            row = c.execute(
                'SELECT id, week, tools FROM records WHERE user_id=? ORDER BY id DESC LIMIT 1',
                (user_id,)
            ).fetchone()
            if row:
                c.execute('DELETE FROM records WHERE id=?', (row['id'],))
                return f'{row["week"]} - {row["tools"]}'
            return None

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
