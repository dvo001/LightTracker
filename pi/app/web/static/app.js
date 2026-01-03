// LightTracking UI - vanilla JS, aligned to current Phase-1 API
const LT_API = {
  state: "/api/v1/state",

  anchorsUpsertPos: "/api/v1/anchors/position",
  anchors: "/api/v1/anchors",
  anchorByMac: (mac) => `/api/v1/anchors/${encodeURIComponent(mac)}`,

  fixtureProfiles: "/api/v1/fixture-profiles",
  fixtures: "/api/v1/fixtures",
  fixtureById: (id) => `/api/v1/fixtures/${id}`,

  calibrationStart: "/api/v1/calibration/start",
  calibrationAbort: "/api/v1/calibration/abort",
  calibrationRuns: "/api/v1/calibration/runs",
  calibrationRunById: (id) => `/api/v1/calibration/runs/${id}`,

  trackingTags: "/api/v1/tracking/tags",
  trackingPos: (tagMac) => `/api/v1/tracking/position/${encodeURIComponent(tagMac)}`,

  events: "/api/v1/events",
  settings: "/api/v1/settings",
  dmxConfig: "/api/v1/dmx/config",
};

function $(id){ return document.getElementById(id); }

async function ltFetchJson(url, opts){
  const o = Object.assign({ headers: {} }, opts || {});
  if (!o.headers["Content-Type"] && o.method && o.method !== "GET") o.headers["Content-Type"] = "application/json";
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

  const st = r.json.system_state ?? "UNKNOWN";
  const mqtt_ok = (r.json.mqtt_ok !== undefined) ? r.json.mqtt_ok : null;
  const anchors = (r.json.anchors_online !== undefined) ? r.json.anchors_online : null;

  if ($("dash_state")) $("dash_state").textContent = st;
  if ($("dash_mqtt")) $("dash_mqtt").textContent = (mqtt_ok === null ? "unknown" : (mqtt_ok ? "OK" : "DOWN"));
  if ($("dash_anchors")) $("dash_anchors").textContent = (anchors === null ? "unknown" : String(anchors));

  const w = [];
  if (mqtt_ok === false) w.push("MQTT nicht verbunden (oder mqtt_ok wird in Phase-1 noch nicht korrekt berechnet).");
  if (typeof anchors === "number" && anchors < 4) w.push("Weniger als 4 Anchors online (Gate für Calibration).");

  if (warnings){
    warnings.innerHTML = (w.length ? w : ["keine"]).map(x => `<li>${escapeHtml(x)}</li>`).join("");
  }
}

// ---------------- Anchors ----------------
async function ltSetAnchorPosition(ev){
  ev.preventDefault();
  if (!await ltAssertNotLive("Set Anchor Position")) return;

  const mac = $("anc_mac").value.trim();
  const x_cm = Number($("anc_x").value);
  const y_cm = Number($("anc_y").value);
  const z_cm = Number($("anc_z").value);

  const payload = { mac, x_cm: Math.trunc(x_cm), y_cm: Math.trunc(y_cm), z_cm: Math.trunc(z_cm) };

  const out = $("anchors_form_out");
  out.textContent = "saving…";
  const r = await ltFetchJson(LT_API.anchorsUpsertPos, { method: "POST", body: JSON.stringify(payload) });
  out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

// ---------------- Anchors List ----------------
async function ltLoadAnchors(){
  const body = $("anchors_tbody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="6" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.anchors);
  if (!r.ok || !r.json){
    body.innerHTML = `<tr><td colspan="6">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }
  const list = r.json?.anchors || [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="6" class="muted">Keine Anchors.</td></tr>`;
    return;
  }
  body.innerHTML = list.map(a => {
    const mac = a.mac || '';
    const alias = a.alias || '';
    const last = a.last_seen_at_ms || '';
    const pos = a.position_cm || {};
    return `
      <tr>
        <td>${escapeHtml(mac)}</td>
        <td>${escapeHtml(alias)}</td>
        <td>${escapeHtml(String(last))}</td>
        <td>${escapeHtml(String(pos.x ?? '?'))}</td>
        <td>${escapeHtml(String(pos.y ?? '?'))}</td>
        <td>${escapeHtml(String(pos.z ?? '?'))}</td>
      </tr>
    `;
  }).join('');
}

// ---------------- Fixtures ----------------
async function ltLoadFixturesTable(){
  const body = $("fx_tbody");
  if (!body) return;

  body.innerHTML = `<tr><td colspan="7" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.fixtures);
  if (!r.ok){
    body.innerHTML = `<tr><td colspan="7">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }

  const list = r.json?.fixtures || [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="7" class="muted">Keine Fixtures.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(fx => {
    const id = fx.id;
    const name = fx.name ?? "";
    const profile = fx.profile_key ?? "";
    const uni = fx.universe ?? "";
    const addr = fx.dmx_base_addr ?? "";
    const p = `${fx.pos_x_cm ?? 0}, ${fx.pos_y_cm ?? 0}, ${fx.pos_z_cm ?? 0}`;
    const enabled = (fx.enabled === 0 || fx.enabled === false) ? false : true;

    return `
      <tr>
        <td>${escapeHtml(String(id))}</td>
        <td>${enabled ? '✔' : '✖'}</td>
        <td>${escapeHtml(name)}</td>
        <td>${escapeHtml(profile)}</td>
        <td>${escapeHtml(String(uni))}</td>
        <td>${escapeHtml(String(addr))}</td>
        <td>${escapeHtml(p)}</td>
        <td class="row">
          <a class="btn" href="/ui/fixtures/${id}/edit">Edit</a>
          <button class="btn danger" onclick="ltDeleteFixture(${id})">Delete</button>
          ${enabled ? `<button class="btn" onclick="ltDisableFixture(${id})">Disable</button>` : `<button class="btn" onclick="ltEnableFixture(${id})">Enable</button>`}
        </td>
      </tr>
    `;
  }).join("");
}

async function ltEnableFixture(id){
  if (!await ltAssertNotLive('Enable Fixture')) return;
  const r = await ltFetchJson(LT_API.fixtureById(id) + '/enable', { method: 'POST' });
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));
  ltLoadFixturesTable();
}

async function ltDisableFixture(id){
  if (!await ltAssertNotLive('Disable Fixture')) return;
  const r = await ltFetchJson(LT_API.fixtureById(id) + '/disable', { method: 'POST' });
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));
  ltLoadFixturesTable();
}

function ltFixturePayloadFromForm(){
  return {
    name: $("fx_name").value.trim(),
    universe: Number($("fx_universe").value),
    dmx_base_addr: Number($("fx_addr").value),
    profile_key: $("fx_profile").value.trim(),
    pos_x_cm: Math.trunc(Number($("fx_x").value || 0)),
    pos_y_cm: Math.trunc(Number($("fx_y").value || 0)),
    pos_z_cm: Math.trunc(Number($("fx_z").value || 0)),
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

  const r = await ltFetchJson(LT_API.fixtureById(id));
  if (!r.ok || !r.json){
    if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
    return;
  }

  $("fx_name").value = r.json.name ?? "";
  $("fx_profile").value = r.json.profile_key ?? "";
  $("fx_universe").value = r.json.universe ?? 1;
  $("fx_addr").value = r.json.dmx_base_addr ?? 1;
  $("fx_x").value = r.json.pos_x_cm ?? 0;
  $("fx_y").value = r.json.pos_y_cm ?? 0;
  $("fx_z").value = r.json.pos_z_cm ?? 0;

  if (out) out.textContent = "";
}

async function ltUpdateFixture(ev, id){
  ev.preventDefault();
  if (!await ltAssertNotLive("Update Fixture")) return;

  const payload = ltFixturePayloadFromForm();
  const out = $("fx_result");
  out.textContent = "saving…";

  const r = await ltFetchJson(LT_API.fixtureById(id), { method: "PUT", body: JSON.stringify(payload) });
  out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (r.ok) window.location.href = "/ui/fixtures";
}

async function ltDeleteFixture(id){
  if (!await ltAssertNotLive("Delete Fixture")) return;
  const ok = confirm(`Fixture wirklich löschen?\n\nID: ${id}`);
  if (!ok) return;

  const r = await ltFetchJson(LT_API.fixtureById(id), { method: "DELETE" });
  if (!r.ok) alert(JSON.stringify(r.json ?? r, null, 2));

  if (window.location.pathname.includes("/edit")) window.location.href = "/ui/fixtures";
  else ltLoadFixturesTable();
}

// ---------------- Calibration ----------------
async function ltCalibrationPrecheck(){
  const r = await ltFetchJson(LT_API.state);
  if (!r.ok || !r.json) return;

  if ($("cal_state")) $("cal_state").textContent = r.json.system_state ?? "UNKNOWN";
  if ($("cal_mqtt")) $("cal_mqtt").textContent = (r.json.mqtt_ok ? "OK" : "DOWN");
  if ($("cal_anchors")) $("cal_anchors").textContent = String(r.json.anchors_online ?? "unknown");
}

async function ltUpdateCalibrationStatus(){
  const out = $("cal_out");
  const r = await ltFetchJson(LT_API.calibrationStatus || '/api/v1/calibration/status');
  if (!r.ok || !r.json){
    if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
    return;
  }

  const s = r.json;
  if ($("cal_state")) $("cal_state").textContent = s.running ? 'RUNNING' : 'IDLE';
  if (out) out.textContent = JSON.stringify(s, null, 2);

  // show commit/discard when finished run present
  if (s.running && s.run_id){
    $("cal_commit_btn").style.display = 'none';
    $("cal_discard_btn").style.display = 'none';
  } else if (!s.running && s.run_id){
    // completed run available
    $("cal_commit_btn").style.display = '';
    $("cal_discard_btn").style.display = '';
  } else {
    $("cal_commit_btn").style.display = 'none';
    $("cal_discard_btn").style.display = 'none';
  }
}

async function ltCalibrationCommit(){
  const id = ($("cal_run_id").value || "").trim();
  if (!id) return alert('run_id fehlt');
  const r = await ltFetchJson(`/api/v1/calibration/commit/${encodeURIComponent(id)}`, { method: 'POST' });
  alert(JSON.stringify(r.json ?? r));
  ltUpdateCalibrationStatus();
}

async function ltCalibrationDiscard(){
  const id = ($("cal_run_id").value || "").trim();
  if (!id) return alert('run_id fehlt');
  const r = await ltFetchJson(`/api/v1/calibration/discard/${encodeURIComponent(id)}`, { method: 'POST' });
  alert(JSON.stringify(r.json ?? r));
  ltUpdateCalibrationStatus();
}

// Attach UI handlers when the DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const commitBtn = document.getElementById('cal_commit_btn');
  const discardBtn = document.getElementById('cal_discard_btn');
  const runIdInput = document.getElementById('cal_run_id');

  if (commitBtn) commitBtn.addEventListener('click', (ev) => { ev.preventDefault(); ltCalibrationCommit(); });
  if (discardBtn) discardBtn.addEventListener('click', (ev) => { ev.preventDefault(); ltCalibrationDiscard(); });

  // start periodic status polling
  ltUpdateCalibrationStatus();
  setInterval(ltUpdateCalibrationStatus, 3000);
});

async function ltCalibrationStart(){
  if (!await ltAssertNotLive("Start Calibration")) return;

  const tagMac = $("cal_tag_mac").value.trim();
  const duration = Number($("cal_duration").value || 6000);
  if (!tagMac) { alert("tag_mac ist Pflicht"); return; }

  const out = $("cal_out");
  if (out) out.textContent = "starting…";

  const r = await ltFetchJson(LT_API.calibrationStart, { method: "POST", body: JSON.stringify({ tag_mac: tagMac, duration_ms: duration }) });
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (r.ok && r.json?.run_id) $("cal_run_id").value = String(r.json.run_id);
}

async function ltCalibrationAbort(){
  const out = $("cal_out");
  if (out) out.textContent = "aborting…";
  const r = await ltFetchJson(LT_API.calibrationAbort, { method: "POST", body: JSON.stringify({}) });
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

async function ltCalibrationLoadRuns(){
  const out = $("cal_runs_out");
  if (out) out.textContent = "loading…";
  const tag = ($("cal_runs_tag_mac").value || "").trim();
  const url = tag ? (LT_API.calibrationRuns + "?tag_mac=" + encodeURIComponent(tag)) : LT_API.calibrationRuns;
  const r = await ltFetchJson(url);
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

async function ltCalibrationLoadSelectedRun(){
  const out = $("cal_runs_out");
  const id = ($("cal_run_id").value || "").trim();
  if (!id) { alert("run_id fehlt"); return; }
  if (out) out.textContent = "loading…";
  const r = await ltFetchJson(LT_API.calibrationRunById(id));
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

// ---------------- Live Monitor ----------------
let ltLiveTimer = null;

function ltLiveStart(){
  ltLiveStop();
  ltLiveTick();
  const ms = Math.max(50, Number($("live_poll_ms")?.value || 300));
  ltLiveTimer = setInterval(ltLiveTick, ms);
}
function ltLiveStop(){
  if (ltLiveTimer) clearInterval(ltLiveTimer);
  ltLiveTimer = null;
}

async function ltLiveTick(){
  const st = await ltGetSystemState();
  if ($("live_state")) $("live_state").textContent = st ?? "unknown";

  let tagMac = ($("live_tag_mac")?.value || "").trim();
  if (!tagMac){
    const rs = await ltFetchJson(LT_API.settings);
    if (rs.ok && rs.json?.settings){
      const item = rs.json.settings.find(s => s.key === "tracking.tag_mac");
      if (item && item.value) tagMac = item.value;
    }
  }
  if (!tagMac){
    const rt = await ltFetchJson(LT_API.trackingTags);
    const tags = rt.json?.tags || [];
    if (tags.length) tagMac = tags[0].tag_mac;
  }

  const out = $("live_out");
  if (!tagMac){
    if ($("live_tracking")) $("live_tracking").textContent = "no tag selected";
    if (out) out.textContent = "Set tracking.tag_mac in Settings oder trage tag_mac ein.";
    return;
  }

  const r = await ltFetchJson(LT_API.trackingPos(tagMac));
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);

  if (!r.ok || !r.json){
    if ($("live_tracking")) $("live_tracking").textContent = "ERR";
    return;
  }

  const status = r.json.state ?? r.json.status ?? "OK";
  const age = r.json.age_ms ?? r.json.age ?? "—";
  const pos = r.json.position_cm ?? r.json.position ?? r.json.pos ?? {};
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

  const r = await ltFetchJson(LT_API.events + "?limit=200");
  if (!r.ok){
    body.innerHTML = `<tr><td colspan="4">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }

  const list = r.json?.events || [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="4" class="muted">Keine Events.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(e => {
    const t = e.ts_ms ?? "";
    const level = e.level ?? "";
    const cat = e.source ?? "";
    const msg = e.event_type ?? "";
    const details = e.details_json ?? "";
    return `
      <tr>
        <td>${escapeHtml(String(t))}</td>
        <td>${escapeHtml(String(level))}</td>
        <td>${escapeHtml(String(cat))}</td>
        <td>${escapeHtml(String(msg))}<div class="muted">${escapeHtml(String(details))}</div></td>
      </tr>
    `;
  }).join("");
}

// ---------------- Settings (Key/Value) ----------------
function ltAddSettingRow(key="", value=""){
  const body = $("settings_tbody");
  if (!body) return;
  const row = document.createElement("tr");
  row.innerHTML = `
    <td><input class="kv_in" value="${escapeHtml(key)}" placeholder="key" /></td>
    <td><input class="kv_in" value="${escapeHtml(value)}" placeholder="value" /></td>
    <td class="row">
      <button class="btn danger" type="button">Remove</button>
    </td>
  `;
  row.querySelector("button").addEventListener("click", () => row.remove());
  body.appendChild(row);
}

async function ltLoadSettings(){
  const out = $("settings_out");
  if (out) out.textContent = "lade…";

  const body = $("settings_tbody");
  if (body) body.innerHTML = `<tr><td colspan="3" class="muted">lade…</td></tr>`;

  const r = await ltFetchJson(LT_API.settings);
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (!r.ok || !r.json) return;

  const items = r.json.settings || [];
  if (body){
    body.innerHTML = "";
    if (!items.length){
      body.innerHTML = `<tr><td colspan="3" class="muted">Keine Settings.</td></tr>`;
    } else {
      for (const it of items) ltAddSettingRow(it.key, it.value);
    }
  }
}

async function ltSaveSettings(){
  if (!await ltAssertNotLive("Save Settings")) return;

  const body = $("settings_tbody");
  const out = $("settings_out");
  if (!body) return;

  const rows = [...body.querySelectorAll("tr")];
  const items = rows.map(r => {
    const ins = r.querySelectorAll("input.kv_in");
    if (ins.length < 2) return null;
    return { key: ins[0].value.trim(), value: ins[1].value };
  }).filter(x => x && x.key);

  out.textContent = "saving… (PUT one-by-one)";

  const results = [];
  for (const it of items){
    const rr = await ltFetchJson(LT_API.settings, { method: "PUT", body: JSON.stringify(it) });
    results.push({ key: it.key, ok: rr.ok, status: rr.status, resp: rr.json });
  }
  out.textContent = JSON.stringify({ saved: results.length, results }, null, 2);
}

// ---------------- DMX / Artnet Config ----------------
async function ltLoadDmxConfig(){
  const out = $("dmx_cfg_out");
  if (out) out.textContent = "lade…";

  const modeEl = $("dmx_mode");
  const uartEl = $("dmx_uart_device");
  const tgtEl = $("artnet_target");
  const portEl = $("artnet_port");
  const uniEl = $("artnet_universe");

  const r = await ltFetchJson(LT_API.dmxConfig);
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
  if (!r.ok || !r.json) return;

  const cfg = r.json.config || {};
  if (modeEl) modeEl.value = cfg.mode || "uart";
  if (uartEl) uartEl.value = cfg.uart_device || "/dev/serial0";
  if (tgtEl) tgtEl.value = cfg.artnet_target || "255.255.255.255";
  if (portEl) portEl.value = cfg.artnet_port ?? 6454;
  if (uniEl) uniEl.value = cfg.artnet_universe ?? 0;
}

async function ltSaveDmxConfig(){
  if (!await ltAssertNotLive("DMX/Artnet Config speichern")) return;
  const out = $("dmx_cfg_out");
  if (out) out.textContent = "saving…";

  const asNumberOrNull = (val, fallback) => {
    const n = Number(val);
    return Number.isFinite(n) ? n : fallback;
  };

  const payload = {
    mode: $("dmx_mode")?.value || "uart",
    uart_device: $("dmx_uart_device")?.value || undefined,
    artnet_target: $("artnet_target")?.value || undefined,
    artnet_port: asNumberOrNull($("artnet_port")?.value, 6454),
    artnet_universe: asNumberOrNull($("artnet_universe")?.value, 0),
  };

  const r = await ltFetchJson(LT_API.dmxConfig, { method: "PUT", body: JSON.stringify(payload) });
  if (out) out.textContent = JSON.stringify(r.json ?? r, null, 2);
}

// Expose to window
window.ltRefreshFooterState = ltRefreshFooterState;
window.ltRefreshDashboard = ltRefreshDashboard;

window.ltSetAnchorPosition = ltSetAnchorPosition;

window.ltLoadFixturesTable = ltLoadFixturesTable;
window.ltCreateFixture = ltCreateFixture;
window.ltLoadFixtureForEdit = ltLoadFixtureForEdit;
window.ltUpdateFixture = ltUpdateFixture;
window.ltDeleteFixture = ltDeleteFixture;

window.ltCalibrationPrecheck = ltCalibrationPrecheck;
window.ltCalibrationStart = ltCalibrationStart;
window.ltCalibrationAbort = ltCalibrationAbort;
window.ltCalibrationLoadRuns = ltCalibrationLoadRuns;
window.ltCalibrationLoadSelectedRun = ltCalibrationLoadSelectedRun;

window.ltLiveStart = ltLiveStart;
window.ltLiveStop = ltLiveStop;
window.ltLiveTick = ltLiveTick;

window.ltLoadEvents = ltLoadEvents;
window.ltLoadSettings = ltLoadSettings;
window.ltSaveSettings = ltSaveSettings;
window.ltAddSettingRow = ltAddSettingRow;
window.ltLoadDmxConfig = ltLoadDmxConfig;
window.ltSaveDmxConfig = ltSaveDmxConfig;
