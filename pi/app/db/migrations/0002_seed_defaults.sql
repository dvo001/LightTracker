-- 0002_seed_defaults.sql
PRAGMA foreign_keys=ON;

INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('system.state','SETUP',strftime('%s','now')*1000);

INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('rates.global','{"tracking_hz":10,"dmx_hz":30,"ui_hz":5,"stale_timeout_ms":5000,"lost_timeout_ms":15000}',strftime('%s','now')*1000);

INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('guards.min_anchors_online','4',strftime('%s','now')*1000);
INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('guards.require_network','false',strftime('%s','now')*1000);

INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('tracking.mode','3D',strftime('%s','now')*1000);
INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('tracking.loss_behavior','freeze',strftime('%s','now')*1000);

INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('dmx.output_driver','uart_rs485',strftime('%s','now')*1000);
INSERT OR REPLACE INTO settings(key,value,updated_at_ms) VALUES('dmx.uart_device','/dev/serial0',strftime('%s','now')*1000);

INSERT OR REPLACE INTO fixture_profiles(profile_key,profile_json,updated_at_ms) VALUES('generic_mh_16bit_v1','{"name":"generic_mh_16bit_v1","channels":16}',strftime('%s','now')*1000);
-- seed defaults
