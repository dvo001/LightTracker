import tempfile
import os
from app.db.migrations.runner import run_migrations
from app.db import connect_db


def test_migrations_create_tables(tmp_path):
    db_path = tmp_path / "test.db"
    os.environ["LT_DB_PATH"] = str(db_path)
    run_migrations(str(db_path))

    conn = connect_db()
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        for required in ["settings", "fixtures", "fixture_profiles", "devices", "device_settings", "event_log", "schema_migrations"]:
            assert required in tables
        # seeds
        cur = conn.execute("SELECT value FROM settings WHERE key='system.state'")
        row = cur.fetchone()
        assert row and row[0] == "SETUP"
    finally:
        conn.close()
