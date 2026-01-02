-- Migration: 0001_base.sql
-- Creates initial schema for LightTracker
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS fixtures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  profile_key TEXT,
  universe INTEGER,
  dmx_base_addr INTEGER,
  pos_x_cm INTEGER,
  pos_y_cm INTEGER,
  pos_z_cm INTEGER
);

CREATE TABLE IF NOT EXISTS fixture_profiles (
  profile_key TEXT PRIMARY KEY,
  profile_json TEXT
);

CREATE TABLE IF NOT EXISTS anchors (
  mac TEXT PRIMARY KEY,
  alias TEXT,
  pos_x_cm INTEGER,
  pos_y_cm INTEGER,
  pos_z_cm INTEGER,
  last_seen_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS anchor_positions (
  mac TEXT PRIMARY KEY,
  x_cm INTEGER,
  y_cm INTEGER,
  z_cm INTEGER,
  updated_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS devices (
  mac TEXT PRIMARY KEY,
  last_seen_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS calibration_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag_mac TEXT,
  started_at_ms INTEGER,
  ended_at_ms INTEGER,
  result TEXT,
  invalidated_at_ms INTEGER,
  params_json TEXT,
  summary_json TEXT
);

CREATE TABLE IF NOT EXISTS schema_migrations (
  id TEXT PRIMARY KEY,
  applied_at_ms INTEGER
);

INSERT OR IGNORE INTO schema_migrations (id, applied_at_ms) VALUES ('0001_base.sql', strftime('%s','now')*1000);

COMMIT;
PRAGMA foreign_keys=ON;
