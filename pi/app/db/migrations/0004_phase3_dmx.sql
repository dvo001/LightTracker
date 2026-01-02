-- Migration: 0004_phase3_dmx.sql
-- Adds DMX/fixture geometry fields required for Phase 3
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

ALTER TABLE fixtures RENAME TO _fixtures_old_v3;

CREATE TABLE fixtures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  profile_key TEXT,
  universe INTEGER,
  dmx_base_addr INTEGER,
  pos_x_cm INTEGER,
  pos_y_cm INTEGER,
  pos_z_cm INTEGER,
  pan_min_deg REAL,
  pan_max_deg REAL,
  tilt_min_deg REAL,
  tilt_max_deg REAL,
  invert_pan INTEGER DEFAULT 0,
  invert_tilt INTEGER DEFAULT 0,
  pan_zero_deg REAL,
  tilt_zero_deg REAL,
  pan_offset_deg REAL,
  tilt_offset_deg REAL,
  slew_pan_deg_s REAL,
  slew_tilt_deg_s REAL,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at_ms INTEGER
);

INSERT INTO fixtures (id,name,profile_key,universe,dmx_base_addr,pos_x_cm,pos_y_cm,pos_z_cm,enabled,updated_at_ms,
  pan_min_deg, pan_max_deg, tilt_min_deg, tilt_max_deg, invert_pan, invert_tilt, pan_zero_deg, tilt_zero_deg, pan_offset_deg, tilt_offset_deg, slew_pan_deg_s, slew_tilt_deg_s)
  SELECT id,name,profile_key,universe,dmx_base_addr,pos_x_cm,pos_y_cm,pos_z_cm,enabled,updated_at_ms,
    0,360,0,180,0,0,0,0,0,0,180,180
  FROM _fixtures_old_v3;
DROP TABLE _fixtures_old_v3;

INSERT OR IGNORE INTO schema_migrations (id, applied_at_ms) VALUES ('0004_phase3_dmx.sql', strftime('%s','now')*1000);

COMMIT;
PRAGMA foreign_keys=ON;
