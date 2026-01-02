import os
import sqlite3

def get_db_path():
    default = os.path.normpath(os.path.join(os.path.dirname(__file__), '..', 'data', 'lighttracker.db'))
    return os.environ.get('LT_DB_PATH', default)

def connect_db():
    path = get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def execute_sql(sql, params=None):
    conn = connect_db()
    try:
        cur = conn.cursor()
        cur.execute(sql, params or [])
        conn.commit()
        return cur
    finally:
        conn.close()
