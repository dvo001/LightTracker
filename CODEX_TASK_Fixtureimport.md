# CODEX TASK FILE — OFL Fixture Import + Fixture Library + Test “Light On”
Project: Existing DMX/UWB BaseStation project (Raspberry Pi + Webserver + SQLite)
Owner: Codex
Priority: High
Scope: Replace any legacy fixture import with OFL-only import. Persist fixtures for re-use. Add a test action to turn on light for a patched fixture.

---

## 1) Objectives

1. Implement **OFL-compatible JSON** fixture import (and only that).
2. Store imported fixtures in a **local fixture library** so users can re-select previously imported hardware without re-upload.
3. Add **Patch** concept (fixture instance): select fixture + mode + DMX universe/address + optional overrides.
4. Provide a **Test Control** that turns on the light at the fixture (minimum viable: set dimmer to full and open shutter, if present).

---

## 2) Definitions / Constraints

- “OFL-compatible” means:
  - Uploaded file is JSON.
  - Contains `$schema` field OR is validated by internal OFL schema validator (see section 4).
  - Contains modes and channel definitions sufficient to produce DMX output.

- All stored fixtures are immutable definitions; user-specific values (DMX address, universe, default mode, pan/tilt inversion, etc.) are stored in a separate patch table.

- DMX output layer already exists in the project. If it does not, implement minimal sender for the active DMX backend (Art-Net/sACN/serial) used by the project.

---

## 3) Deliverables

### 3.1 Backend
- Endpoint to **upload/import** OFL JSON fixture
- Endpoints to **list/search** fixtures
- Endpoint to **create/update/list** patched fixtures (fixture instances)
- Endpoint to **run test**: turn on light for a patched fixture
- Validation + duplicate detection + error reporting

### 3.2 Persistence (SQLite)
- New tables:
  - `fixtures`
  - `patched_fixtures`

### 3.3 Web UI
- Fixture Library page:
  - Upload OFL JSON
  - List/search manufacturer/model
  - View modes (names + channel count)
- Patch page:
  - Create patched fixture: choose fixture + mode + universe + address + name
- Test page (or patch details):
  - Button: “Light ON (Test)”
  - Button: “Light OFF (Test)” (recommended)
  - Show what channels were written for the test

---

## 4) Implementation Plan

### 4.1 Data Model

#### Table: `fixtures`
- `id` INTEGER PRIMARY KEY
- `manufacturer` TEXT NOT NULL
- `model` TEXT NOT NULL
- `ofl_schema` TEXT NULL           -- extracted from `$schema`
- `ofl_json` TEXT NOT NULL         -- normalized JSON string
- `content_hash` TEXT NOT NULL     -- sha256(normalized_json)
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
Indexes:
- unique(`content_hash`)
- index(`manufacturer`, `model`)

#### Table: `patched_fixtures`
- `id` INTEGER PRIMARY KEY
- `fixture_id` INTEGER NOT NULL REFERENCES fixtures(id)
- `name` TEXT NOT NULL
- `mode_name` TEXT NOT NULL
- `universe` INTEGER NOT NULL      -- 0/1-based according to existing system; document in UI
- `dmx_address` INTEGER NOT NULL   -- 1..512
- `overrides_json` TEXT NULL       -- optional user overrides
- `created_at` TEXT NOT NULL
- `updated_at` TEXT NOT NULL
Indexes:
- index(`fixture_id`)
- index(`name`)

### 4.2 OFL Import Pipeline

1. Parse JSON.
2. Validate “basic” requirements:
   - must be JSON object
   - must contain `modes` array (or OFL equivalent in your accepted subset)
3. Validate against OFL schema:
   - Option A (preferred): bundle a pinned OFL JSON schema version inside project and validate with jsonschema.
   - Option B: accept `$schema` but still validate against pinned supported schemas only.
4. Normalize:
   - sort keys, remove insignificant whitespace
   - compute sha256 hash over normalized JSON
5. Duplicate detection:
   - if `content_hash` exists → return existing fixture id (idempotent import)
6. Extract `manufacturer`, `model`:
   - Use OFL structure (may require reading these from file path in OFL repo; for upload we require fields inside JSON or supply fields in upload form).
   - If JSON does not include manufacturer/model fields: require user to provide them in the upload form, store as columns.
7. Store.

Acceptance criteria:
- Invalid OFL JSON returns HTTP 400 with a specific message.
- Duplicate upload returns existing fixture id; does not create duplicates.

### 4.3 Fixture Search/List
- Search by manufacturer/model substring (case-insensitive).
- Return fixture id + manufacturer + model + available modes summary.

### 4.4 Patch Management
- Create patched fixture:
  - Validate `dmx_address` within [1..512]
  - Validate selected `mode_name` exists in fixture definition
  - Validate `dmx_address + mode_channel_count - 1 <= 512`
- Store patch.

### 4.5 DMX Test: “Light ON”
Goal: Turn on the light reliably for typical fixtures.

Implementation logic (minimum viable, robust):
1. Build DMX frame of size 512 initialized to 0.
2. Compute start index = `dmx_address - 1`.
3. Determine which channel(s) to set:
   - Always set **primary dimmer/intensity** channel to 255 if present.
   - If fixture has **shutter/strobe** channel:
     - set to a value that corresponds to “Open” (often lowest range after 0; but not guaranteed).
4. If exact “Open” value cannot be inferred from capabilities:
   - Provide two strategies:
     - Strategy A (capability-aware): if OFL includes capability ranges with “Open” keyword → choose midpoint of that range.
     - Strategy B (fallback): set shutter to 255 and dimmer to 255, and optionally set strobe to 0; expose a UI toggle “Try max shutter”.
5. Write frame to DMX output on the given universe.

Also implement “Light OFF”:
- Set dimmer to 0, shutter to 0; send frame.

Acceptance criteria:
- User can press “Light ON” and the fixture emits light on common fixtures with a dimmer channel.
- If fixture requires shutter open, system attempts it; if not determinable, UI indicates which channels were forced and allows a fallback.

Observability:
- Return payload containing:
  - patched_fixture_id
  - universe/address
  - channel writes (channel number → value)
  - any warnings (e.g., “no dimmer channel found; wrote shutter only”)

---

## 5) API Specification (suggested)

### Fixtures
- POST `/api/fixtures/import/ofl`
  - multipart/form-data: `file` (json), optional `manufacturer`, `model`
  - response: `{ fixture_id, duplicate: boolean, warnings: [] }`

- GET `/api/fixtures`
  - query: `q=...`
  - response: list of `{ id, manufacturer, model, modes:[{name, channels}] }`

- GET `/api/fixtures/:id`
  - response: `{ id, manufacturer, model, ofl_json, modes... }`

### Patched fixtures
- POST `/api/patched-fixtures`
  - body: `{ fixture_id, name, mode_name, universe, dmx_address, overrides_json? }`
  - response: `{ id }`

- GET `/api/patched-fixtures`
  - response: list

- GET `/api/patched-fixtures/:id`
  - response: patch details + referenced fixture summary

### Test control
- POST `/api/patched-fixtures/:id/test/light-on`
- POST `/api/patched-fixtures/:id/test/light-off`
  - response: `{ writes:[{channel,value}], warnings:[] }`

---

## 6) UI Tasks

1. Add “Fixture Library” nav item:
   - Upload widget (accept .json)
   - Search bar
   - Table: Manufacturer | Model | Modes | Actions (View, Patch)
2. Add “Patch Fixture” form:
   - Select fixture
   - Select mode
   - Universe (dropdown or number)
   - DMX address
   - Save
3. Patch details page:
   - Show computed channel count and address range
   - Buttons: Light ON / Light OFF
   - Show last test write log (channels written)

---

## 7) Testing

### Unit tests
- JSON validation:
  - valid OFL fixture imports successfully
  - invalid JSON rejected
  - missing required structure rejected
- Duplicate import:
  - same file twice returns same fixture id
- Patch validation:
  - address overflow rejected

### Integration tests
- Create patch and run Light ON:
  - asserts DMX output function called with correct universe and 512-byte frame
  - asserts dimmer channel set to 255 when present

---

## 8) Notes / Decisions Required (Codex to infer from existing code)
- Identify existing DMX backend and how to send frames (module/function).
- Identify existing DB access layer and migration mechanism; implement schema migration accordingly.
- Identify web framework routing conventions and match them.

End of task file.
