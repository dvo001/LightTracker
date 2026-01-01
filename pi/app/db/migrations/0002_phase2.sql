-- Migration: 0002_phase2.sql
-- Adds Phase-2 columns: fixtures.enabled, fixtures.updated_at_ms
-- and calibration_runs.status, committed_at_ms, discarded_at_ms
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

-- Add fixtures.enabled and fixtures.updated_at_ms if not present
ALTER TABLE fixtures RENAME TO _fixtures_old;
CREATE TABLE fixtures (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT,
  profile_key TEXT,
  universe INTEGER,
  dmx_base_addr INTEGER,
  pos_x_cm INTEGER,
  pos_y_cm INTEGER,
  pos_z_cm INTEGER,
  enabled INTEGER NOT NULL DEFAULT 1,
  updated_at_ms INTEGER
);
INSERT INTO fixtures (id,name,profile_key,universe,dmx_base_addr,pos_x_cm,pos_y_cm,pos_z_cm)
  SELECT id,name,profile_key,universe,dmx_base_addr,pos_x_cm,pos_y_cm,pos_z_cm FROM _fixtures_old;
DROP TABLE _fixtures_old;

-- Add calibration_runs fields if not present
ALTER TABLE calibration_runs RENAME TO _cal_old;
CREATE TABLE calibration_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tag_mac TEXT,
  started_at_ms INTEGER,
  ended_at_ms INTEGER,
  result TEXT,
  invalidated_at_ms INTEGER,
  params_json TEXT,
  summary_json TEXT,
  status TEXT,
  committed_at_ms INTEGER,
  discarded_at_ms INTEGER
);
INSERT INTO calibration_runs (id,tag_mac,started_at_ms,ended_at_ms,result,invalidated_at_ms,params_json,summary_json)
  SELECT id,tag_mac,started_at_ms,ended_at_ms,result,invalidated_at_ms,params_json,summary_json FROM _cal_old;
DROP TABLE _cal_old;

COMMIT;
PRAGMA foreign_keys=ON;
