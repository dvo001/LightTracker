import os
import sqlite3
from glob import glob

MIGRATIONS_DIR = os.path.dirname(__file__)
DB_DEFAULT = os.path.normpath(os.path.join(MIGRATIONS_DIR, '..', '..', 'data', 'lighttracker.db'))

def get_db_path():
    return os.environ.get('LT_DB_PATH', DB_DEFAULT)

def ensure_migrations_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS schema_migrations (
        id TEXT PRIMARY KEY,
        applied_at_ms INTEGER
    )''')
    conn.commit()

def applied_migrations(conn):
    cur = conn.execute('SELECT id FROM schema_migrations')
    return {row[0] for row in cur.fetchall()}

def apply_migration_file(conn, path):
    sql = open(path, 'r', encoding='utf-8').read()
    conn.executescript(sql)
    mid = os.path.basename(path)
    conn.execute('INSERT OR REPLACE INTO schema_migrations (id, applied_at_ms) VALUES (?, strftime("%s","now")*1000)', (mid,))
    conn.commit()

def run_migrations(db_path=None):
    db_path = db_path or get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        ensure_migrations_table(conn)
        applied = applied_migrations(conn)
        files = sorted(glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
        for f in files:
            mid = os.path.basename(f)
            if mid in applied:
                continue
            apply_migration_file(conn, f)
    finally:
        conn.close()

if __name__ == '__main__':
    print('Running migrations against', get_db_path())
    run_migrations()
