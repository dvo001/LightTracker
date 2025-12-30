import os
import tempfile
import sqlite3


def test_migrations_run(monkeypatch):
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tmp.close()
    db_path = tmp.name
    monkeypatch.setenv('PI_DB_PATH', db_path)

    # import app code and run migrations
    from app.db.persistence import get_persistence

    p = get_persistence()
    p.migrate()

    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {r[0] for r in cur.fetchall()}
    assert 'devices' in names
    assert 'settings' in names
    assert 'event_log' in names
    conn.close()
