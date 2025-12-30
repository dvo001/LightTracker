-- 0001_init_schema.sql
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS devices (
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

CREATE TABLE IF NOT EXISTS device_settings (
    mac TEXT,
    key TEXT,
    value TEXT,
    updated_at_ms INTEGER,
    PRIMARY KEY(mac,key)
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS anchor_positions (
    mac TEXT PRIMARY KEY,
    x_cm INTEGER,
    y_cm INTEGER,
    z_cm INTEGER,
    updated_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS fixture_profiles (
    profile_key TEXT PRIMARY KEY,
    profile_json TEXT,
    updated_at_ms INTEGER
);

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_key TEXT,
    anchor_mac TEXT,
    notes TEXT
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

CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts_ms INTEGER,
    level TEXT,
    source TEXT,
    event_type TEXT,
    ref TEXT,
    details_json TEXT
);
-- initial schema
