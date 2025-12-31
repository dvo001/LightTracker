// LightTracking UI - vanilla JS (no build chain)
const LT_API = {
  state: "/api/v1/state",
  anchors: "/api/v1/anchors",
  anchorPos: "/api/v1/anchors/position",          // fallback; may differ
  fixtures: "/api/v1/fixtures",
  calibrationStart: "/api/v1/calibration/start",
  calibrationAbort: "/api/v1/calibration/abort",
  calibrationStatus: "/api/v1/calibration/status",
  calibrationCommit: "/api/v1/calibration/commit",
  calibrationDiscard: "/api/v1/calibration/discard",
  tracking: "/api/v1/tracking",
  trackingPosition: "/api/v1/tracking/position",
  events: "/api/v1/events",
  settings: "/api/v1/settings",
};

function $(id){ return document.getElementById(id); }

async function ltFetchJson(url, opts){
  const o = Object.assign({ headers: {} }, opts || {});
  if (!o.headers["Content-Type"] && o.method && o.method !== "GET") {
    o.headers["Content-Type"] = "application/json";
  }
  try{
    const r = await fetch(url, o);
    let j = null;
    try { j = await r.json(); } catch { j = null; }
    return { ok: r.ok, status: r.status, json: j };
  } catch (e){
    return { ok:false, status: 0, json: { error: String(e) } };
  }
}

function escapeHtml(s){
  return String(s ?? "")
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

async function ltGetSystemState(){
  const r = await ltFetchJson(LT_API.state);
  if (!r.ok || !r.json) return null;
  return r.json.system_state || r.json.state || null;
}

async function ltRefreshFooterState(){
  const st = await ltGetSystemState();
  const el = $("lt_footer_state");
  if (el) el.textContent = "state: " + (st ?? "unknown");
}

async function ltAssertNotLive(actionName){
  const st = await ltGetSystemState();
  if (st === "LIVE") {
    alert(`Aktion "${actionName}" ist in LIVE gesperrt.`);
    return false;
  }
  return true;
}

// ---------------- Dashboard ----------------
async function ltRefreshDashboard(){
  const out = $("dash_debug");
  const warnings = $("dash_warnings");
  const r = await ltFetchJson(LT_API.state);
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);

  if (!r.ok || !r.json){
    if ($("dash_state")) $("dash_state").textContent = "ERROR";
    if (warnings) warnings.innerHTML = `<li>State endpoint nicht erreichbar: ${escapeHtml(JSON.stringify(r.json))}</li>`;
    return;
  }

  const st = r.json.system_state ?? r.json.state ?? "UNKNOWN";
  const mqtt_ok = (r.json.mqtt_ok !== undefined) ? r.json.mqtt_ok : (r.json.mqtt?.ok ?? null);
  const anchors = r.json.anchors_online ?? r.json.anchors?.online ?? null;

  if ($("dash_state")) $("dash_state").textContent = st;
  if ($("dash_mqtt")) $("dash_mqtt").textContent = (mqtt_ok === null ? "unknown" : (mqtt_ok ? "OK" : "DOWN"));
  if ($("dash_anchors")) $("dash_anchors").textContent = (anchors === null ? "unknown" : String(anchors));

  const w = [];
  if (mqtt_ok === false) w.push("MQTT nicht verbunden");
  if (typeof anchors === "number" && anchors < 4) w.push("Weniger als 4 Anchors online");
  if (st === "LIVE" && mqtt_ok === false) w.push("LIVE, aber MQTT down (kritisch)");

  if (warnings){
    warnings.innerHTML = (w.length ? w : ["keine"]).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  }
}

// ---------------- Anchors ----------------
let ltSelectedAnchor = null;

function ltAnchorId(a){
  return a.mac || a.id || a.anchor_id || a.uuid || "";
}

function ltBadge(enabled){
  if (enabled === false) return `<span class="badge off">DISABLED</span>`;
  return `<span class="badge on">ENABLED</span>`;
}

async function ltLoadAnchors(){
  const body = $("anchors_tbody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="6" class="muted">lade…</td></tr>`;

  const r = await ltFetchJson(LT_API.anchors);
  if (!r.ok){
    body.innerHTML = `<tr><td colspan="6">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }

  const list = Array.isArray(r.json) ? r.json : (r.json.items || r.json.anchors || []);
  if (!list.length){
    body.innerHTML = `<tr><td colspan="6" class="muted">Keine Anchors.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(a => {
    const mac = ltAnchorId(a);
    const name = a.name ?? a.label ?? "";
    const online = (a.online !== undefined) ? a.online : (a.is_online ?? null);
    const last = a.last_seen ?? a.lastSeen ?? a.last_seen_ts ?? "";
    const pos = a.position_cm ?? a.position ?? {};
    const p = `${pos.x ?? ""}, ${pos.y ?? ""}, ${pos.z ?? ""}`;
    const enabled = (a.enabled === false) ? false : true;

    const status = online === null ? "unknown" : (online ? "online" : "offline");

    return `
      <tr>
        <td><button class="btn" onclick='ltSelectAnchor(${JSON.stringify(a)})'>${escapeHtml(mac)}</button></td>
        <td>${escapeHtml(name)}</td>
        <td>${ltBadge(enabled)} <span class="muted">${escapeHtml(status)}</span></td>
        <td>${escapeHtml(String(last))}</td>
        <td>${escapeHtml(p)}</td>
        <td class="row">
          <button class="btn" onclick="ltPrefillAnchor('${escapeHtml(mac)}','${escapeHtml(name)}',${pos.x ?? 0},${pos.y ?? 0},${pos.z ?? 0})">Prefill</button>
        </td>
      </tr>
    `;
  }).join("");
}

function ltSelectAnchor(a){
  ltSelectedAnchor = a;
  alert("Anchor selected: " + (a.mac || a.id || "unknown"));
}

function ltPrefillAnchor(mac, name, x, y, z){
  $("anc_mac").value = mac;
  $("anc_name").value = name || "";
  $("anc_x").value = x ?? 0;
  $("anc_y").value = y ?? 0;
  $("anc_z").value = z ?? 0;
}

function ltPrefillFromSelectedAnchor(){
  if (!ltSelectedAnchor) {
    alert("Kein Anchor ausgewählt.");
    return;
  }
  const a = ltSelectedAnchor;
  const pos = a.position_cm ?? a.position ?? {};
  ltPrefillAnchor(a.mac || a.id || "", a.name || a.label || "", pos.x ?? 0, pos.y ?? 0, pos.z ?? 0);
}

async function ltSetAnchorPosition(ev){
  ev.preventDefault();
  if (!await ltAssertNotLive("Set Anchor Position")) return;

  const mac = $("anc_mac").value.trim();
  const name = $("anc_name").value.trim();
  const x = Number($("anc_x").value);
  const y = Number($("anc_y").value);
  const z = Number($("anc_z").value);

  const payloadCandidates = [
    { mac, name, position_cm: { x, y, z } },
    { mac, name, x_cm: x, y_cm: y, z_cm: z },
    { mac, name, position: { x, y, z } },
  ];

  // try common endpoints/payloads - if your API differs, adjust LT_API.anchorPos + payload
  const out = $("anchors_form_out");
  out.textContent = "saving…";

  // First try PUT /api/v1/anchors/{mac}/position if supported
  let r = await ltFetchJson(`${LT_API.anchors}/${encodeURIComponent(mac)}/position`, { method: "PUT", body: JSON.stringify(payloadCandidates[0]) });
  if (!r.ok) {
    // fallback: POST /api/v1/anchors/position
    r = await ltFetchJson(LT_API.anchorPos, { method: "POST", body: JSON.stringify(payloadCandidates[0]) });
  }
  if (!r.ok) {
    // last fallback: PUT /api/v1/anchors/{mac}
    r = await ltFetchJson(`${LT_API.anchors}/${encodeURIComponent(mac)}`, { method: "PUT", body: JSON.stringify(payloadCandidates[0]) });
  }

  out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (r.ok) ltLoadAnchors();
}

// ---------------- Fixtures ----------------
function ltFixtureId(fx){
  return fx.id || fx.fixture_id || fx.uuid || fx.name;
}

async function ltLoadFixturesTable(){
  const body = $("fx_tbody");
  if (!body) return;

  body.innerHTML = `<tr><td colspan="7" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.fixtures);
  if (!r.ok){
    body.innerHTML = `<tr><td colspan="7">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }

  const list = Array.isArray(r.json) ? r.json : (r.json.items || r.json.fixtures || []);
  if (!list.length){
    body.innerHTML = `<tr><td colspan="7" class="muted">Keine Fixtures.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(fx => {
    const id = ltFixtureId(fx);
    const name = fx.name ?? "";
    const profile = fx.profile ?? fx.profile_name ?? "";
    const dmx = fx.dmx ?? {};
    const uni = dmx.universe ?? fx.universe ?? "";
    const addr = dmx.address ?? fx.address ?? fx.dmx_address ?? "";
    const pos = fx.position_cm ?? fx.position ?? {};
    const p = `${pos.x ?? ""}, ${pos.y ?? ""}, ${pos.z ?? ""}`;
    const enabled = (fx.enabled === false) ? false : true;

    const toggleBtn = enabled
      ? `<button class="btn" onclick="ltDisableFixture('${encodeURIComponent(id)}')">Disable</button>`
      : `<button class="btn" onclick="ltEnableFixture('${encodeURIComponent(id)}')">Enable</button>`;

    return `
      <tr>
        <td>${escapeHtml(name)}</td>
        <td>${escapeHtml(profile)}</td>
        <td>${escapeHtml(String(uni))}</td>
        <td>${escapeHtml(String(addr))}</td>
        <td>${ltBadge(enabled)}</td>
        <td>${escapeHtml(p)}</td>
        <td class="row">
          <a class="btn" href="/ui/fixtures/${encodeURIComponent(id)}/edit">Edit</a>
          ${toggleBtn}
          <button class="btn danger" onclick="ltDeleteFixture('${encodeURIComponent(id)}')">Delete</button>
        </td>
      </tr>
    `;
  }).join("");
}

function ltFixturePayloadFromForm(){
  const name = $("fx_name").value.trim();
  const profile = $("fx_profile").value.trim();
  const universe = Number($("fx_universe").value);
  const addr = Number($("fx_addr").value);

  const x = Number($("fx_x").value || 0);
  const y = Number($("fx_y").value || 0);
  const z = Number($("fx_z").value || 0);

  const pan_ch = $("fx_pan_ch").value ? Number($("fx_pan_ch").value) : null;
  const tilt_ch = $("fx_tilt_ch").value ? Number($("fx_tilt_ch").value) : null;
  const dim_ch = $("fx_dim_ch").value ? Number($("fx_dim_ch").value) : null;

  const invert_pan = $("fx_invert_pan").checked;
  const invert_tilt = $("fx_invert_tilt").checked;

  return {
    name,
    profile,
    dmx: { universe, address: addr },
    position_cm: { x, y, z },
    mapping: { pan_ch, tilt_ch, dimmer_ch: dim_ch, invert_pan, invert_tilt }
  };
}

async function ltCreateFixture(ev){
  ev.preventDefault();
  if (!await ltAssertNotLive("Create Fixture")) return;

  const payload = ltFixturePayloadFromForm();
  const out = $("fx_result");
  out.textContent = "saving…";

  const r = await ltFetchJson(LT_API.fixtures, { method: "POST", body: JSON.stringify(payload) });
  out.textContent = JSON.stringify(r.json ?? r, null, 2);

  if (r.ok) window.location.href = "/ui/fixtures";
}

async function ltLoadFixtureForEdit(id){
  const out = $("fx_result");
  if (out) out.textContent = "lade…";

  // try GET /fixtures/{id}; fallback to list and search by id/name
  let r = await ltFetchJson(`${LT_API.fixtures}/${encodeURIComponent(id)}`);
  if (!r.ok){
    const rl = await ltFetchJson(LT_API.fixtures);
    if (rl.ok){
      const list = Array.isArray(rl.json) ? rl.json : (rl.json.items || rl.json.fixtures || []);
      const found = list.find(f => String(ltFixtureId(f)) === String(id) || String(f.name) === String(id));
      if (found) r = { ok:true, status:200, json: found };
    }
  }

  if (!r.ok){
    if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
    return;
  }

  const fx = r.json;
  $("fx_name").value = fx.name ?? "";
  $("fx_profile").value = fx.profile ?? fx.profile_name ?? "";

  const dmx = fx.dmx ?? {};
  $("fx_universe").value = dmx.universe ?? fx.universe ?? 0;
  $("fx_addr").value = dmx.address ?? fx.address ?? 1;

  const pos = fx.position_cm ?? fx.position ?? {};
  $("fx_x").value = pos.x ?? 0;
  $("fx_y").value = pos.y ?? 0;
  $("fx_z").value = pos.z ?? 0;

  const mapping = fx.mapping ?? fx.dmx_mapping ?? {};
  $("fx_pan_ch").value = mapping.pan_ch ?? "";
  $("fx_tilt_ch").value = mapping.tilt_ch ?? "";
  $("fx_dim_ch").value = mapping.dimmer_ch ?? mapping.dim_ch ?? "";
  $("fx_invert_pan").checked = !!mapping.invert_pan;
  $("fx_invert_tilt").checked = !!mapping.invert_tilt;

  if (out) out.textContent = "";
}

async function ltUpdateFixture(ev, id){
  ev.preventDefault();
  if (!await ltAssertNotLive("Update Fixture")) return;

  const payload = ltFixturePayloadFromForm();
  const out = $("fx_result");
  out.textContent = "saving…";

  // try PUT then PATCH
  let r = await ltFetchJson(`${LT_API.fixtures}/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(payload) });
  if (!r.ok){
    r = await ltFetchJson(`${LT_API.fixtures}/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify(payload) });
  }

  out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (r.ok) window.location.href = "/ui/fixtures";
}

async function ltDeleteFixture(id){
  if (!await ltAssertNotLive("Delete Fixture")) return;
  const ok = confirm(`Fixture wirklich löschen?

ID: ${decodeURIComponent(id)}`);
  if (!ok) return;

  const r = await ltFetchJson(`${LT_API.fixtures}/${id}`, { method: "DELETE" });
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));

  if (window.location.pathname.includes("/edit")) window.location.href = "/ui/fixtures";
  else ltLoadFixturesTable();
}

async function ltDisableFixture(id){
  if (!await ltAssertNotLive("Disable Fixture")) return;
  let r = await ltFetchJson(`${LT_API.fixtures}/${id}/disable`, { method: "POST", body: JSON.stringify({}) });
  if (!r.ok){
    // fallback: PATCH enabled=false
    r = await ltFetchJson(`${LT_API.fixtures}/${id}`, { method: "PATCH", body: JSON.stringify({ enabled: false }) });
  }
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));
  ltLoadFixturesTable();
}

async function ltEnableFixture(id){
  if (!await ltAssertNotLive("Enable Fixture")) return;
  let r = await ltFetchJson(`${LT_API.fixtures}/${id}/enable`, { method: "POST", body: JSON.stringify({}) });
  if (!r.ok){
    r = await ltFetchJson(`${LT_API.fixtures}/${id}`, { method: "PATCH", body: JSON.stringify({ enabled: true }) });
  }
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));
  ltLoadFixturesTable();
}

// ---------------- Calibration Wizard ----------------
let ltCalTimer = null;

async function ltCalibrationPrecheck(){
  const pre = $("cal_precheck");
  if (pre) pre.innerHTML = `<li class="muted">lade…</li>`;
  const r = await ltFetchJson(LT_API.state);
  if (!r.ok || !r.json){
    if (pre) pre.innerHTML = `<li>State endpoint nicht erreichbar.</li>`;
    return;
  }
  const st = r.json.system_state ?? r.json.state ?? "UNKNOWN";
  const mqtt_ok = (r.json.mqtt_ok !== undefined) ? r.json.mqtt_ok : null;
  const anchors = r.json.anchors_online ?? null;

  if ($("cal_state")) $("cal_state").textContent = st;
  if ($("cal_mqtt")) $("cal_mqtt").textContent = (mqtt_ok === null ? "unknown" : (mqtt_ok ? "OK" : "DOWN"));
  if ($("cal_anchors")) $("cal_anchors").textContent = (anchors === null ? "unknown" : String(anchors));

  const issues = [];
  if (st === "LIVE") issues.push("State ist LIVE: Calibration gesperrt.");
  if (typeof anchors === "number" && anchors < 4) issues.push("Nicht genug Anchors online (min 4).");
  if (mqtt_ok === false) issues.push("MQTT down (kann ok sein, aber meist unerwünscht).");

  if (pre){
    pre.innerHTML = (issues.length ? issues : ["OK"]).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  }
}

async function ltCalibrationStart(){
  if (!await ltAssertNotLive("Start Calibration")) return;
  const out = $("cal_out");
  if (out) out.textContent = "starting…";

  const r = await ltFetchJson(LT_API.calibrationStart, { method: "POST", body: JSON.stringify({}) });
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);

  if (r.ok){
    ltCalibrationStartPolling();
  }
}

async function ltCalibrationAbort(){
  if (!await ltAssertNotLive("Abort Calibration")) return;
  const out = $("cal_out");
  if (out) out.textContent = "aborting…";

  const r = await ltFetchJson(LT_API.calibrationAbort, { method: "POST", body: JSON.stringify({}) });
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);

  ltCalibrationStopPolling();
}

function ltCalibrationStartPolling(){
  ltCalibrationStopPolling();
  ltCalTimer = setInterval(ltCalibrationPollOnce, 800);
}

function ltCalibrationStopPolling(){
  if (ltCalTimer) clearInterval(ltCalTimer);
  ltCalTimer = null;
}

async function ltCalibrationPollOnce(){
  const r = await ltFetchJson(LT_API.calibrationStatus);
  if ($("cal_status")) $("cal_status").textContent = r.json?.status ?? (r.ok ? "OK" : "ERR");
  if ($("cal_progress")) $("cal_progress").textContent = r.json?.progress ?? r.json?.samples ?? "—";
  const out = $("cal_out");
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

async function ltCalibrationCommit(){
  if (!await ltAssertNotLive("Commit Calibration")) return;
  const r = await ltFetchJson(LT_API.calibrationCommit, { method: "POST", body: JSON.stringify({}) });
  $("cal_out").textContent = JSON.stringify(r.json ?? r, null, 2);
}

async function ltCalibrationDiscard(){
  if (!await ltAssertNotLive("Discard Calibration")) return;
  const r = await ltFetchJson(LT_API.calibrationDiscard, { method: "POST", body: JSON.stringify({}) });
  $("cal_out").textContent = JSON.stringify(r.json ?? r, null, 2);
}

// ---------------- Live Monitor ----------------
let ltLiveTimer = null;

function ltLiveStart(){
  ltLiveStop();
  ltLiveTick();
  ltLiveTimer = setInterval(ltLiveTick, 300); // ~3.3 Hz
}
function ltLiveStop(){
  if (ltLiveTimer) clearInterval(ltLiveTimer);
  ltLiveTimer = null;
}

async function ltLiveTick(){
  const st = await ltGetSystemState();
  if ($("live_state")) $("live_state").textContent = st ?? "unknown";

  // try trackingPosition then tracking
  let r = await ltFetchJson(LT_API.trackingPosition);
  if (!r.ok) r = await ltFetchJson(LT_API.tracking);

  const out = $("live_out");
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);

  const j = r.json || {};
  const status = j.status ?? j.tracking_status ?? (r.ok ? "OK" : "ERR");
  const age = j.age_ms ?? j.age ?? "—";
  const pos = j.position_cm ?? j.position ?? j.pos ?? {};
  const p = `${pos.x ?? "?"}, ${pos.y ?? "?"}, ${pos.z ?? "?"}`;

  if ($("live_tracking")) $("live_tracking").textContent = status;
  if ($("live_age")) $("live_age").textContent = String(age);
  if ($("live_pos")) $("live_pos").textContent = p;
}

// ---------------- Logs / Events ----------------
async function ltLoadEvents(){
  const body = $("log_tbody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="4" class="muted">lade…</td></tr>`;

  const lvl = $("log_level") ? $("log_level").value : "";
  const q = $("log_q") ? $("log_q").value.trim().toLowerCase() : "";

  // try query params if supported
  const url = new URL(LT_API.events, window.location.origin);
  url.searchParams.set("limit", "200");
  if (lvl) url.searchParams.set("level", lvl);
  if (q) url.searchParams.set("q", q);

  const r = await ltFetchJson(url.pathname + url.search);
  if (!r.ok){
    body.innerHTML = `<tr><td colspan="4">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }

  const list = Array.isArray(r.json) ? r.json : (r.json.items || r.json.events || []);
  const filtered = list.filter(e => {
    const elvl = String(e.level ?? e.severity ?? "").toUpperCase();
    const msg = String(e.message ?? e.msg ?? "").toLowerCase();
    const cat = String(e.category ?? e.source ?? "").toLowerCase();
    if (lvl && elvl !== lvl) return false;
    if (q && !(msg.includes(q) || cat.includes(q))) return false;
    return true;
  });

  if (!filtered.length){
    body.innerHTML = `<tr><td colspan="4" class="muted">Keine Events.</td></tr>`;
    return;
  }

  body.innerHTML = filtered.map(e => {
    const t = e.time ?? e.ts ?? e.timestamp ?? "";
    const level = e.level ?? e.severity ?? "";
    const cat = e.category ?? e.source ?? "";
    const msg = e.message ?? e.msg ?? JSON.stringify(e);
    return `
      <tr>
        <td>${escapeHtml(String(t))}</td>
        <td>${escapeHtml(String(level))}</td>
        <td>${escapeHtml(String(cat))}</td>
        <td>${escapeHtml(String(msg))}</td>
      </tr>
    `;
  }).join("");
}

// ---------------- Settings ----------------
async function ltLoadSettings(){
  const out = $("settings_out");
  if (out) out.textContent = "lade…";

  const r = await ltFetchJson(LT_API.settings);
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (!r.ok || !r.json) return;

  // map common names (be liberal)
  $("set_mqtt_host").value = r.json.mqtt_host ?? r.json.mqtt?.host ?? "";
  $("set_mqtt_port").value = r.json.mqtt_port ?? r.json.mqtt?.port ?? "";
  $("set_tracking_hz").value = r.json.tracking_hz ?? r.json.tracking_rate_hz ?? "";
  $("set_dmx_hz").value = r.json.dmx_hz ?? r.json.dmx_rate_hz ?? "";
  $("set_min_anchors").value = r.json.min_anchors ?? r.json.min_anchors_required ?? "";
}

async function ltSaveSettings(){
  if (!await ltAssertNotLive("Save Settings")) return;

  const payload = {
    mqtt_host: $("set_mqtt_host").value.trim() || null,
    mqtt_port: $("set_mqtt_port").value ? Number($("set_mqtt_port").value) : null,
    tracking_hz: $("set_tracking_hz").value ? Number($("set_tracking_hz").value) : null,
    dmx_hz: $("set_dmx_hz").value ? Number($("set_dmx_hz").value) : null,
    min_anchors: $("set_min_anchors").value ? Number($("set_min_anchors").value) : null,
  };

  const out = $("settings_out");
  out.textContent = "saving…";

  // try PUT then POST
  let r = await ltFetchJson(LT_API.settings, { method: "PUT", body: JSON.stringify(payload) });
  if (!r.ok) r = await ltFetchJson(LT_API.settings, { method: "POST", body: JSON.stringify(payload) });

  out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

// Expose to window for onclick handlers
window.ltRefreshFooterState = ltRefreshFooterState;
window.ltRefreshDashboard = ltRefreshDashboard;

window.ltLoadAnchors = ltLoadAnchors;
window.ltSetAnchorPosition = ltSetAnchorPosition;
window.ltPrefillFromSelectedAnchor = ltPrefillFromSelectedAnchor;

window.ltLoadFixturesTable = ltLoadFixturesTable;
window.ltCreateFixture = ltCreateFixture;
window.ltLoadFixtureForEdit = ltLoadFixtureForEdit;
window.ltUpdateFixture = ltUpdateFixture;
window.ltDeleteFixture = ltDeleteFixture;
window.ltDisableFixture = ltDisableFixture;
window.ltEnableFixture = ltEnableFixture;

window.ltCalibrationPrecheck = ltCalibrationPrecheck;
window.ltCalibrationStart = ltCalibrationStart;
window.ltCalibrationAbort = ltCalibrationAbort;
window.ltCalibrationPollOnce = ltCalibrationPollOnce;
window.ltCalibrationCommit = ltCalibrationCommit;
window.ltCalibrationDiscard = ltCalibrationDiscard;

window.ltLiveStart = ltLiveStart;
window.ltLiveStop = ltLiveStop;
window.ltLiveTick = ltLiveTick;

window.ltLoadEvents = ltLoadEvents;
window.ltLoadSettings = ltLoadSettings;
window.ltSaveSettings = ltSaveSettings;
