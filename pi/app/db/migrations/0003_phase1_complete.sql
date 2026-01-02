-- Migration: 0003_phase1_complete.sql
-- Completes Phase 1 schema: device_settings, event_log, seeds, WAL/foreign_keys hints
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- device_settings table
CREATE TABLE IF NOT EXISTS device_settings (
  mac TEXT,
  key TEXT,
  value TEXT,
  updated_at_ms INTEGER,
  PRIMARY KEY(mac, key)
);

-- settings table already exists; ensure updated_at_ms column
ALTER TABLE settings RENAME TO _settings_old;
CREATE TABLE settings (
  key TEXT PRIMARY KEY,
  value TEXT,
  updated_at_ms INTEGER
);
INSERT INTO settings (key,value,updated_at_ms)
  SELECT key,value,updated_at_ms FROM _settings_old;
DROP TABLE _settings_old;

-- event_log
CREATE TABLE IF NOT EXISTS event_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER,
  level TEXT,
  source TEXT,
  event_type TEXT,
  ref TEXT,
  details_json TEXT
);

-- optional logs (empty by default, can be removed later)
CREATE TABLE IF NOT EXISTS position_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER,
  tag_mac TEXT,
  x_cm REAL,
  y_cm REAL,
  z_cm REAL,
  state TEXT,
  anchors_used INTEGER,
  resid_m REAL,
  quality REAL
);

CREATE TABLE IF NOT EXISTS range_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_ms INTEGER,
  anchor_mac TEXT,
  tag_mac TEXT,
  d_m REAL,
  quality REAL,
  nlos INTEGER,
  err INTEGER
);

-- Add richer device fields
ALTER TABLE devices RENAME TO _devices_old;
CREATE TABLE devices (
  mac TEXT PRIMARY KEY,
  role TEXT,
  alias TEXT,
  name TEXT,
  ip_last TEXT,
  fw TEXT,
  first_seen_at_ms INTEGER,
  last_seen_at_ms INTEGER,
  status TEXT,
  notes TEXT
);
INSERT OR IGNORE INTO devices(mac,last_seen_at_ms)
  SELECT mac, last_seen_at_ms FROM _devices_old;
DROP TABLE _devices_old;

-- Seed defaults
INSERT OR IGNORE INTO settings(key, value, updated_at_ms) VALUES
  ('system.state', 'SETUP', strftime('%s','now')*1000),
  ('rates.global', '{"tracking_hz":10,"dmx_hz":30,"ui_hz":2,"stale_timeout_ms":1500,"lost_timeout_ms":4000}', strftime('%s','now')*1000),
  ('guards.min_anchors_online', '4', strftime('%s','now')*1000),
  ('tracking.mode', '3D', strftime('%s','now')*1000),
  ('tracking.loss_behavior', 'freeze', strftime('%s','now')*1000),
  ('dmx.output_driver', 'uart_rs485', strftime('%s','now')*1000),
  ('dmx.uart_device', '/dev/serial0', strftime('%s','now')*1000),
  ('logging.position_log.enabled', 'false', strftime('%s','now')*1000),
  ('logging.position_log.hz', '5', strftime('%s','now')*1000);

INSERT OR IGNORE INTO fixture_profiles(profile_key, profile_json) VALUES
  ('generic_mh_16bit_v1', '{"v":1,"name":"generic 16-bit mover","channels":4,"pan_coarse":1,"pan_fine":2,"tilt_coarse":3,"tilt_fine":4}');

INSERT OR IGNORE INTO schema_migrations (id, applied_at_ms) VALUES ('0003_phase1_complete.sql', strftime('%s','now')*1000);

COMMIT;
PRAGMA foreign_keys=ON;
