# CODEX TASK – Phase 3 (Fixtures + DMX Mapping + UART-RS485 Driver + DMX API)

## Ziel (Phase 3 Scope)
Implementiere Phase 3 im Repo **LightTracking**:
1) **Fixture Profiles + Fixtures CRUD** (DB + API)
2) **DMX Mapping** (Pan/Tilt Mathematik, Limits, Invert, Offsets, Slew Limiter)
3) **DMX Frame Builder** (Universe 1, 512 slots, 16-bit channels)
4) **UART→RS485 Driver** (250k 8N2, best-effort break/MAB)
5) **DMX Engine Tick** (freeze behavior, test-aim)
6) DMX/Fixtures API Endpoints gemäß OpenAPI v1

**Nicht enthalten in Phase 3:** Calibration Workflow (Phase 4), Hardening (MQTTS), advanced UI.

## Harte Vorgaben
- DMX Bewegung nur, wenn `system.state == LIVE` UND Position state == TRACKING.
- Bei STALE/LOST oder nicht LIVE: Freeze (letzter Frame / letzte Fixture-Commands).
- 16-bit Pan/Tilt Default. Pan 0° = +X, Tilt gemäß Elevation.
- Determinismus + Rate-Limiter: Slew limiter muss unabhängig vom Tick-Jitter stabil arbeiten.
- Kein Crash bei UART Fehlern: event_log ERROR + Transition zu SAFE (Policy v1).

---

## Deliverables (Phase 3)

### A) DB: Fixtures + Fixture Profiles voll nutzbar
**Dateien:**
- `pi/app/db/migrations/*` (nur wenn Schema-Erweiterung nötig)
- `pi/app/db/persistence.py` (CRUD)

**Fixtures minimal required fields:**
- id (int PK)
- name (text)
- universe (int, default 1)
- dmx_base_addr (1..512)
- profile_key (FK)
- pos_x_cm, pos_y_cm, pos_z_cm
- pan_min_deg, pan_max_deg, tilt_min_deg, tilt_max_deg
- invert_pan (0/1), invert_tilt (0/1)
- pan_zero_deg, tilt_zero_deg, pan_offset_deg, tilt_offset_deg
- slew_pan_deg_s, slew_tilt_deg_s
- is_enabled (0/1)
- updated_at_ms

**Seed:**
- Ensure `fixture_profiles` contains `generic_mh_16bit_v1` with JSON describing channels:
  - pan_coarse, pan_fine, tilt_coarse, tilt_fine (plus optional dimmer)
  - channel_count at least 4

### B) API: Fixtures + Profiles
**Dateien:**
- `pi/app/api/routes_fixtures.py`
- `pi/app/api/routes_dmx.py`
- `pi/app/api/routes_fixtures.py` should implement:
  - `GET /api/v1/fixture-profiles`
  - `GET /api/v1/fixtures`
  - `POST /api/v1/fixtures`
  - `PUT /api/v1/fixtures/{id}`
  - `DELETE /api/v1/fixtures/{id}`

Validation:
- DMX address range and “fits in 512” using profile channel count
- min<max for pan/tilt
- universe >=1

### C) DMX Mapping (math + constraints)
**Dateien:**
- `pi/app/dmx/mapping.py`

Implement functions:
- `compute_pan_tilt(fixture_pos_cm, target_pos_cm) -> (pan_deg, tilt_deg)`
  - v = target - fixture
  - pan = atan2(v_y, v_x) in degrees
  - tilt = atan2(v_z, sqrt(v_x^2+v_y^2)) in degrees
- apply:
  - invert_pan/tilt
  - offsets (pan_offset_deg, tilt_offset_deg)
  - zero references (pan_zero_deg, tilt_zero_deg) as baseline
  - clamp to min/max
- shortest path for pan (wrap around), respecting limits (v1: implement wrap logic with clamp)
- slew limiter:
  - `limit(prev_deg, target_deg, max_deg_per_s, dt_s) -> new_deg`
  - dt derived from monotonic time between ticks (not fixed)

Unit tests:
- angle correctness quadrants
- clamp behavior
- slew limiter: step-limited movement

### D) DMX Frame Builder
**Dateien:**
- `pi/app/dmx/frame_builder.py`

Implement:
- `build_frame(fixtures_commands, profiles) -> bytes`
- Universe 1, 512 slots + startcode 0x00 (total 513 bytes to send)
- 16-bit mapping: coarse = high byte, fine = low byte
- Provide helper:
  - `u16_to_coarse_fine(value_0_65535)`
  - `deg_to_u16(pan_deg, pan_min, pan_max)` linear mapping
- Ensure channels do not overlap: base addr + channel_count -1 <= 512

### E) UART RS485 Driver
**Dateien:**
- `pi/app/dmx/uart_rs485_driver.py`

Implement best-effort DMX serial output on Linux:
- Open serial device from setting `dmx.uart_device`
- Configure 250000 baud, 8N2 (two stop bits)
- Implement break:
  - if possible: `termios.tcsendbreak()` or serial-specific break
  - else: documented fallback (send with small pause) + event_log WARN once
- Optional DE/RE GPIO toggling if `dmx.rs485_de_gpio` set:
  - use `lgpio` or `RPi.GPIO` (choose one; document dependency)
  - if library unavailable: degrade gracefully with WARN (assume transceiver always enabled)
- Exceptions: log and signal DMX Engine.

### F) DMX Engine Tick + Test Aim
**Dateien:**
- `pi/app/dmx/dmx_engine.py`
- integrate with `state_manager` and `tracking_engine` caches

Behavior:
- tick at `rates.global.dmx_hz`
- if `system.state==LIVE` and pos.state==TRACKING:
  - compute commands for each enabled fixture
  - apply slew limiter per fixture
  - build frame and send
- else:
  - freeze (reuse last frame)
- `POST /api/v1/dmx/aim` (SETUP only):
  - set test mode for duration_ms
  - target_cm from request
  - during test, ignore tag position and aim all fixtures at target
- `POST /api/v1/dmx/stop` stops test mode immediately

Error policy:
- If send_frame fails repeatedly: log ERROR + `state_manager.set_state(SAFE)`

### G) Tests (minimum)
Under `pi/app/tests/`:
1) `test_mapping.py` (angles, clamp, slew)
2) `test_frame_builder.py` (channel placement, bytes length, u16 mapping)
3) `test_fixtures_api.py` (CRUD + validation)
4) `test_dmx_engine_smoke.py`:
   - simulate system state LIVE + fake position
   - assert send_frame called with correct length and nonzero channels

---

## Definition of Done (Phase 3)
- Fixtures CRUD works and persists in SQLite.
- DMX mapping + frame builder are unit-tested and correct.
- DMX engine runs and outputs frames (driver may be mocked in CI).
- Freeze behavior works for STALE/LOST and non-LIVE states.
- DMX aim test works in SETUP only.
- Errors are logged and trigger SAFE where specified.
