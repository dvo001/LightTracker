-- Migration: 0005_ofl_fixtures.sql
-- Adds OFL fixture library and patched fixtures tables
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS ofl_fixtures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  manufacturer TEXT NOT NULL,
  model TEXT NOT NULL,
  ofl_schema TEXT,
  ofl_json TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ofl_fixtures_hash ON ofl_fixtures(content_hash);
CREATE INDEX IF NOT EXISTS idx_ofl_fixtures_make_model ON ofl_fixtures(manufacturer, model);

CREATE TABLE IF NOT EXISTS patched_fixtures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  fixture_id INTEGER NOT NULL REFERENCES ofl_fixtures(id),
  name TEXT NOT NULL,
  mode_name TEXT NOT NULL,
  universe INTEGER NOT NULL,
  dmx_address INTEGER NOT NULL,
  overrides_json TEXT,
  created_at_ms INTEGER NOT NULL,
  updated_at_ms INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_patched_fixtures_fixture ON patched_fixtures(fixture_id);
CREATE INDEX IF NOT EXISTS idx_patched_fixtures_name ON patched_fixtures(name);

INSERT OR IGNORE INTO schema_migrations (id, applied_at_ms) VALUES ('0005_ofl_fixtures.sql', strftime('%s','now')*1000);

COMMIT;
PRAGMA foreign_keys=ON;
