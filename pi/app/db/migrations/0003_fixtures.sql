-- 0003_fixtures.sql
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS fixtures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    universe INTEGER DEFAULT 1,
    dmx_base_addr INTEGER,
    profile_key TEXT,
    pos_x_cm INTEGER,
    pos_y_cm INTEGER,
    pos_z_cm INTEGER,
    pan_min_deg REAL,
    pan_max_deg REAL,
    tilt_min_deg REAL,
    tilt_max_deg REAL,
    invert_pan INTEGER DEFAULT 0,
    invert_tilt INTEGER DEFAULT 0,
    pan_zero_deg REAL DEFAULT 0,
    tilt_zero_deg REAL DEFAULT 0,
    pan_offset_deg REAL DEFAULT 0,
    tilt_offset_deg REAL DEFAULT 0,
    slew_pan_deg_s REAL DEFAULT 180.0,
    slew_tilt_deg_s REAL DEFAULT 180.0,
    is_enabled INTEGER DEFAULT 1,
    updated_at_ms INTEGER
);
