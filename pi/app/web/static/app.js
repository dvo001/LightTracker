// LightTracking UI - vanilla JS, aligned to current Phase-1 API
const LT_API = {
  state: "/api/v1/state",

  anchorsUpsertPos: "/api/v1/anchors/position",
  anchors: "/api/v1/anchors",
  anchorByMac: (mac) => `/api/v1/anchors/${encodeURIComponent(mac)}`,

  fixtureProfiles: "/api/v1/fixture-profiles",
  fixtureProfileImportSsl2: "/api/v1/fixture-profiles/import-ssl2",
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
  devices: "/api/v1/devices",
  deviceByMac: (mac) => `/api/v1/devices/${encodeURIComponent(mac)}`,
  deviceApplySettings: (mac) => `/api/v1/devices/${encodeURIComponent(mac)}/apply-settings`,
  dmxConfig: "/api/v1/dmx/config",
  oflFixtures: "/api/v1/ofl/fixtures",
  oflImport: "/api/v1/ofl/fixtures/import",
  oflPatchedFixtures: "/api/v1/ofl/patched-fixtures",
  oflPatchedFixture: (id) => `/api/v1/ofl/patched-fixtures/${id}`,
  oflTestOn: (id) => `/api/v1/ofl/patched-fixtures/${id}/test/light-on`,
  oflTestOff: (id) => `/api/v1/ofl/patched-fixtures/${id}/test/light-off`,
};

function $(id){ return document.getElementById(id); }

async function ltFetchJson(url, opts){
  const o = Object.assign({ headers: {} }, opts || {});
  if (!o.headers["Content-Type"] && o.method && o.method !== "GET") o.headers["Content-Type"] = "application/json";
  try{
    const r = await fetch(url, o);
    let j = null;
    try { j = await r.json(); } catch (e) { j = null; }
    return { ok: r.ok, status: r.status, json: j };
  } catch (e){
    return { ok:false, status: 0, json: { error: String(e) } };
  }
}

function escapeHtml(s){
  return String((s === undefined || s === null) ? "" : s)
    .replaceAll("&","&amp;")
    .replaceAll("<","&lt;")
    .replaceAll(">","&gt;")
    .replaceAll('"',"&quot;")
    .replaceAll("'","&#039;");
}

let LT_WIFI_DEFAULTS = { ssid: "", pass: "" };
let LT_MQTT_DEFAULTS = { host: "", port: 1883 };

function nz(v, fallback){
  return (v === undefined || v === null) ? fallback : v;
}

function ltNormalizeMac(mac){
  return (mac || "").replace(/[^a-fA-F0-9]/g, "").toUpperCase();
}

function ltFormatMacColon(mac){
  const hex = ltNormalizeMac(mac).slice(0, 12);
  let out = "";
  for (let i = 0; i < hex.length; i++){
    if (i > 0 && i % 2 === 0) out += ":";
    out += hex[i];
  }
  return out;
}

function ltAttachMacFormatter(el){
  if (!el) return;
  el.addEventListener("input", () => {
    const formatted = ltFormatMacColon(el.value);
    el.value = formatted;
  });
}

async function ltGetSystemState(){
  const r = await ltFetchJson(LT_API.state);
  if (!r.ok || !r.json) return null;
  return r.json.system_state || r.json.state || null;
}

function ltApplyDefaultsToForms(force=false){
  const maybeSet = (id, val) => {
    const el = $(id);
    if (el && (force || !el.value)) el.value = val;
  };
  maybeSet("dev_cfg_ssid", LT_WIFI_DEFAULTS.ssid);
  maybeSet("dev_cfg_pass", LT_WIFI_DEFAULTS.pass);
  maybeSet("tag_cfg_ssid", LT_WIFI_DEFAULTS.ssid);
  maybeSet("tag_cfg_pass", LT_WIFI_DEFAULTS.pass);
  maybeSet("dev_cfg_mqtthost", LT_MQTT_DEFAULTS.host);
  maybeSet("dev_cfg_mqttport", LT_MQTT_DEFAULTS.port);
  maybeSet("tag_cfg_host", LT_MQTT_DEFAULTS.host);
  maybeSet("tag_cfg_port", LT_MQTT_DEFAULTS.port);
}

async function ltLoadSystemDefaults(){
  const out = $("net_default_out");
  if (out) out.textContent = "lade…";
  const r = await ltFetchJson(LT_API.settings);
  if (!r.ok || !r.json){
    if (out) out.textContent = `Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}`;
    return;
  }
  const items = r.json.settings || [];
  const ssid = (items.find((i) => i.key === "wifi.ssid") || {}).value || "";
  const pass = (items.find((i) => i.key === "wifi.pass") || {}).value || "";
  const host = (items.find((i) => i.key === "mqtt.host") || {}).value || "";
  const portRaw = (items.find((i) => i.key === "mqtt.port") || {}).value || "";
  const port = Number(portRaw) || 1883;
  LT_WIFI_DEFAULTS = { ssid, pass };
  LT_MQTT_DEFAULTS = { host, port };

  const ssidField = $("wifi_ssid");
  const passField = $("wifi_pass");
  if (ssidField) ssidField.value = ssid;
  if (passField) passField.value = pass;
  const hostField = $("mqtt_host");
  const portField = $("mqtt_port");
  if (hostField) hostField.value = host;
  if (portField) portField.value = port;

  ltApplyDefaultsToForms(true);
  if (out) out.textContent = "geladen";
}

async function ltSaveSystemDefaults(ev){
  if (ev && ev.preventDefault) ev.preventDefault();
  const ssidEl = $("wifi_ssid");
  const passEl = $("wifi_pass");
  const hostEl = $("mqtt_host");
  const portEl = $("mqtt_port");
  const ssid = (ssidEl ? ssidEl.value : "").trim();
  const pass = passEl ? passEl.value : "";
  const host = (hostEl ? hostEl.value : "").trim();
  const port = Number(portEl ? portEl.value : 0);
  const out = $("net_default_out");
  if (out) out.textContent = "sende…";
  const payloads = [
    { key: "wifi.ssid", value: ssid },
    { key: "wifi.pass", value: pass },
    { key: "mqtt.host", value: host },
    { key: "mqtt.port", value: String(port || 1883) },
  ];
  const results = [];
  for (const it of payloads){
    const r = await ltFetchJson(LT_API.settings, { method: "PUT", body: JSON.stringify(it) });
    results.push({ key: it.key, ok: r.ok, status: r.status, resp: r.json });
    if (!r.ok && r.json && r.json.detail && r.json.detail.code === "STATE_BLOCKED"){
      alert("Settings können im LIVE state nicht geändert werden.");
      break;
    }
  }
  LT_WIFI_DEFAULTS = { ssid, pass };
  LT_MQTT_DEFAULTS = { host, port: port || 1883 };
  ltApplyDefaultsToForms(true);
  if (out) out.textContent = JSON.stringify({ saved: results }, null, 2);
}

async function ltLoadWifiDefaults(){
  return ltLoadSystemDefaults();
}

function ltBuildDefaultConfig(alias){
  const payload = {};
  const { ssid, pass } = LT_WIFI_DEFAULTS;
  const { host, port } = LT_MQTT_DEFAULTS;
  if (ssid) payload.wifi_ssid = ssid;
  if (ssid || pass) payload.wifi_pass = pass;
  if (host) payload.mqtt_host = host;
  const p = Number(port);
  if (p) payload.mqtt_port = p;
  if (alias) payload.alias = alias;
  return payload;
}

async function ltSendDeviceConfig(mac, alias, outEl){
  const macNorm = ltNormalizeMac(mac || "");
  if (!mac){
    alert("MAC fehlt");
    return;
  }
  if (!macNorm){
    alert("MAC-Format ungültig");
    return;
  }
  const payload = ltBuildDefaultConfig(alias);
  if (!Object.keys(payload).length){
    alert("Keine Default-Config gesetzt (WiFi/MQTT/Alias).");
    return;
  }
  if (outEl) outEl.textContent = "sende…";
  const r = await ltFetchJson(LT_API.deviceApplySettings(macNorm), { method: "POST", body: JSON.stringify(payload) });
  if (outEl) outEl.textContent = JSON.stringify((r.json || r), null, 2);
  if (!r.ok) alert("Senden fehlgeschlagen");
}

async function ltRefreshFooterState(){
  const st = await ltGetSystemState();
  const el = $("lt_footer_state");
  if (el) el.textContent = "state: " + nz(st, "unknown");
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
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);

  if (!r.ok || !r.json){
    if ($("dash_state")) $("dash_state").textContent = "ERROR";
    if (warnings) warnings.innerHTML = `<li>State endpoint nicht erreichbar: ${escapeHtml(JSON.stringify(r.json))}</li>`;
    return;
  }

  const st = r.json.system_state === undefined || r.json.system_state === null ? "UNKNOWN" : r.json.system_state;
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
  out.textContent = JSON.stringify((r.json || r), null, 2);
}

// ---------------- Anchors List ----------------
async function ltLoadAnchors(){
  const body = $("anchors_tbody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="7" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.anchors);
  if (!r.ok || !r.json){
    body.innerHTML = `<tr><td colspan="7">Fehler: ${escapeHtml(JSON.stringify(r.json))}</td></tr>`;
    return;
  }
  const list = (r.json && r.json.anchors) ? r.json.anchors : [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="7" class="muted">Keine Anchors.</td></tr>`;
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
        <td>${escapeHtml(String(nz(pos.x,'?')))}</td>
        <td>${escapeHtml(String(nz(pos.y,'?')))}</td>
        <td>${escapeHtml(String(nz(pos.z,'?')))}</td>
        <td class="row">
          <button class="btn" onclick="ltSendAnchorConfig('${mac}','${alias.replace(/'/g,'&#39;')}')">Send Config</button>
        </td>
      </tr>
    `;
  }).join('');
}

function ltSendAnchorConfig(mac, alias){
  const formMacEl = $("anc_mac");
  const formAliasEl = $("anc_alias");
  const formMac = formMacEl ? formMacEl.value : "";
  const formAlias = formAliasEl ? formAliasEl.value : "";
  const useAlias = ltNormalizeMac(formMac) === ltNormalizeMac(mac) && formAlias ? formAlias : alias;
  ltSendDeviceConfig(mac, useAlias, $("anchors_form_out"));
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

  const list = (r.json && r.json.fixtures) ? r.json.fixtures : [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="7" class="muted">Keine Fixtures.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(fx => {
    const id = fx.id;
    const name = nz(fx.name, "");
    const profile = nz(fx.profile_key, "");
    const uni = nz(fx.universe, "");
    const addr = nz(fx.dmx_base_addr, "");
    const p = `${nz(fx.pos_x_cm, 0)}, ${nz(fx.pos_y_cm, 0)}, ${nz(fx.pos_z_cm, 0)}`;
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
  if (!r.ok) alert(JSON.stringify((r.json || r), null, 2));
  ltLoadFixturesTable();
}

async function ltDisableFixture(id){
  if (!await ltAssertNotLive('Disable Fixture')) return;
  const r = await ltFetchJson(LT_API.fixtureById(id) + '/disable', { method: 'POST' });
  if (!r.ok) alert(JSON.stringify((r.json || r), null, 2));
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
  out.textContent = JSON.stringify((r.json || r), null, 2);

  if (r.ok) window.location.href = "/ui/fixtures";
}

async function ltLoadFixtureForEdit(id){
  const out = $("fx_result");
  if (out) out.textContent = "lade…";

  const r = await ltFetchJson(LT_API.fixtureById(id));
  if (!r.ok || !r.json){
    if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
    return;
  }

  $("fx_name").value = nz(r.json.name, "");
  $("fx_profile").value = nz(r.json.profile_key, "");
  $("fx_universe").value = nz(r.json.universe, 1);
  $("fx_addr").value = nz(r.json.dmx_base_addr, 1);
  $("fx_x").value = nz(r.json.pos_x_cm, 0);
  $("fx_y").value = nz(r.json.pos_y_cm, 0);
  $("fx_z").value = nz(r.json.pos_z_cm, 0);

  if (out) out.textContent = "";
}

async function ltUpdateFixture(ev, id){
  ev.preventDefault();
  if (!await ltAssertNotLive("Update Fixture")) return;

  const payload = ltFixturePayloadFromForm();
  const out = $("fx_result");
  out.textContent = "saving…";

  const r = await ltFetchJson(LT_API.fixtureById(id), { method: "PUT", body: JSON.stringify(payload) });
  out.textContent = JSON.stringify((r.json || r), null, 2);
  if (r.ok) window.location.href = "/ui/fixtures";
}

async function ltDeleteFixture(id){
  if (!await ltAssertNotLive("Delete Fixture")) return;
  const ok = confirm(`Fixture wirklich löschen?\n\nID: ${id}`);
  if (!ok) return;

  const r = await ltFetchJson(LT_API.fixtureById(id), { method: "DELETE" });
  if (!r.ok) alert(JSON.stringify((r.json || r), null, 2));

  if (window.location.pathname.includes("/edit")) window.location.href = "/ui/fixtures";
  else ltLoadFixturesTable();
}

// ---------------- Calibration ----------------
async function ltCalibrationPrecheck(){
  const r = await ltFetchJson(LT_API.state);
  if (!r.ok || !r.json) return;

  if ($("cal_state")) $("cal_state").textContent = nz(r.json.system_state, "UNKNOWN");
  if ($("cal_mqtt")) $("cal_mqtt").textContent = (r.json.mqtt_ok ? "OK" : "DOWN");
  if ($("cal_anchors")) $("cal_anchors").textContent = String(nz(r.json.anchors_online, "unknown"));
}

async function ltUpdateCalibrationStatus(){
  const out = $("cal_out");
  const r = await ltFetchJson(LT_API.calibrationStatus || '/api/v1/calibration/status');
  if (!r.ok || !r.json){
    if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
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
  alert(JSON.stringify((r.json || r)));
  ltUpdateCalibrationStatus();
}

async function ltCalibrationDiscard(){
  const id = ($("cal_run_id").value || "").trim();
  if (!id) return alert('run_id fehlt');
  const r = await ltFetchJson(`/api/v1/calibration/discard/${encodeURIComponent(id)}`, { method: 'POST' });
  alert(JSON.stringify((r.json || r)));
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
  if (out) out.textContent = JSON.stringify(r.json || r, null, 2);
  if (r.ok && r.json && r.json.run_id) $("cal_run_id").value = String(r.json.run_id);
}

async function ltCalibrationAbort(){
  const out = $("cal_out");
  if (out) out.textContent = "aborting…";
  const r = await ltFetchJson(LT_API.calibrationAbort, { method: "POST", body: JSON.stringify({}) });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
}

async function ltCalibrationLoadRuns(){
  const out = $("cal_runs_out");
  if (out) out.textContent = "loading…";
  const tag = ($("cal_runs_tag_mac").value || "").trim();
  const url = tag ? (LT_API.calibrationRuns + "?tag_mac=" + encodeURIComponent(tag)) : LT_API.calibrationRuns;
  const r = await ltFetchJson(url);
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
}

async function ltCalibrationLoadSelectedRun(){
  const out = $("cal_runs_out");
  const id = ($("cal_run_id").value || "").trim();
  if (!id) { alert("run_id fehlt"); return; }
  if (out) out.textContent = "loading…";
  const r = await ltFetchJson(LT_API.calibrationRunById(id));
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
}

// ---------------- Live Monitor ----------------
let ltLiveTimer = null;

function ltLiveStart(){
  ltLiveStop();
  ltLiveTick();
  const lpm = $("live_poll_ms");
  const ms = Math.max(50, Number(lpm ? lpm.value : 300));
  ltLiveTimer = setInterval(ltLiveTick, ms);
}
function ltLiveStop(){
  if (ltLiveTimer) clearInterval(ltLiveTimer);
  ltLiveTimer = null;
}

async function ltLiveTick(){
  const st = await ltGetSystemState();
  if ($("live_state")) $("live_state").textContent = nz(st, "unknown");

  const ltm = $("live_tag_mac");
  let tagMac = (ltm ? ltm.value : "").trim();
  if (!tagMac){
    const rs = await ltFetchJson(LT_API.settings);
    if (rs.ok && rs.json && rs.json.settings){
      const item = rs.json.settings.find(s => s.key === "tracking.tag_mac");
      if (item && item.value) tagMac = item.value;
    }
  }
  if (!tagMac){
    const rt = await ltFetchJson(LT_API.trackingTags);
    const tags = (rt.json && rt.json.tags) ? rt.json.tags : [];
    if (tags.length) tagMac = tags[0].tag_mac;
  }

  const out = $("live_out");
  if (!tagMac){
    if ($("live_tracking")) $("live_tracking").textContent = "no tag selected";
    if (out) out.textContent = "Set tracking.tag_mac in Settings oder trage tag_mac ein.";
    return;
  }

  const r = await ltFetchJson(LT_API.trackingPos(tagMac));
  if (out) out.textContent = JSON.stringify(r.json || r, null, 2);

  if (!r.ok || !r.json){
    if ($("live_tracking")) $("live_tracking").textContent = "ERR";
    return;
  }

  const status = nz(r.json.state, nz(r.json.status, "OK"));
  const age = nz(r.json.age_ms, nz(r.json.age, "—"));
  const pos = nz(r.json.position_cm, nz(r.json.position, nz(r.json.pos, {})));
  const p = `${nz(pos.x, "?")}, ${nz(pos.y, "?")}, ${nz(pos.z, "?")}`;

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

  const list = (r.json && r.json.events) ? r.json.events : [];
  if (!list.length){
    body.innerHTML = `<tr><td colspan="4" class="muted">Keine Events.</td></tr>`;
    return;
  }

  body.innerHTML = list.map(e => {
    const t = nz(e.ts_ms, "");
    const level = nz(e.level, "");
    const cat = nz(e.source, "");
    const msg = nz(e.event_type, "");
    const details = nz(e.details_json, "");
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

// ---------------- Device Config (WiFi/MQTT) ----------------
async function ltApplyDeviceSettings(ev){
  if (ev && ev.preventDefault) ev.preventDefault();
  const mac_raw = ( $("dev_cfg_mac") ? $("dev_cfg_mac").value : "" ).trim();
  const mac = ltNormalizeMac(mac_raw);
  const out = $("dev_cfg_out");
  if (!mac_raw){
    alert("MAC-Adresse ist erforderlich");
    return;
  }
  if (!mac){
    alert("MAC-Format ungültig");
    return;
  }
  const payload = {};
  const ssid = ( $("dev_cfg_ssid") ? $("dev_cfg_ssid").value : "" ).trim();
  const pass = $("dev_cfg_pass") ? $("dev_cfg_pass").value : "";
  const host = ( $("dev_cfg_mqtthost") ? $("dev_cfg_mqtthost").value : "" ).trim();
  const port = Number($("dev_cfg_mqttport") ? $("dev_cfg_mqttport").value : 0);
  const batch = Number($("dev_cfg_batch") ? $("dev_cfg_batch").value : 0);
  const hb = Number($("dev_cfg_heartbeat") ? $("dev_cfg_heartbeat").value : 0);
  const alias = ( $("dev_cfg_alias") ? $("dev_cfg_alias").value : "" ).trim();

  if (ssid) payload.wifi_ssid = ssid;
  if (pass || ssid) payload.wifi_pass = pass;
  if (host) payload.mqtt_host = host;
  if (port) payload.mqtt_port = port;
  if (batch) payload.batch_period_ms = batch;
  if (hb) payload.heartbeat_ms = hb;
  if (alias) payload.alias = alias;

  if (!Object.keys(payload).length){
    alert("Keine Einstellungen gesetzt.");
    return;
  }

  if (out) out.textContent = "sende…";
  const r = await ltFetchJson(LT_API.deviceApplySettings(mac), { method: "POST", body: JSON.stringify(payload) });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
  if (!r.ok) alert("Senden fehlgeschlagen. Siehe Ausgabe.");
}

async function ltLoadTags(){
  const body = $("tags_tbody");
  if (!body) return;
  const filter = ( $("tag_filter_mac") ? $("tag_filter_mac").value : "" ).trim().toLowerCase();
  body.innerHTML = `<tr><td colspan="5" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.devices);
  if (!r.ok || !r.json){
    body.innerHTML = `<tr><td colspan="5">Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}</td></tr>`;
    return;
  }
  const list = (r.json.devices || []).filter(d => (d.role || "").toUpperCase() === "TAG");
  const filtered = filter ? list.filter(d => (d.mac || "").toLowerCase().includes(filter) || (d.alias || "").toLowerCase().includes(filter)) : list;
  if (!filtered.length){
    body.innerHTML = `<tr><td colspan="5" class="muted">Keine Tags.</td></tr>`;
    return;
  }
  body.innerHTML = filtered.map(d => {
    const mac = d.mac || "";
    const alias = d.alias || "";
    const status = d.status || "";
    const last = d.last_seen_at_ms ? new Date(d.last_seen_at_ms).toLocaleString() : "";
    return `
      <tr>
        <td>${escapeHtml(mac)}</td>
        <td>${escapeHtml(alias)}</td>
        <td>${escapeHtml(status)}</td>
        <td>${escapeHtml(last)}</td>
        <td class="row">
          <button class="btn" onclick="ltSendTagConfig('${mac}','${alias.replace(/'/g,'&#39;')}')">Send Config</button>
          <button class="btn" onclick="ltTagPrefill('${mac}', '${alias.replace(/'/g,'&#39;')}')">Edit</button>
        </td>
      </tr>
    `;
  }).join("");
}

function ltTagPrefill(mac, alias){
  const m = $("tag_cfg_mac");
  const a = $("tag_cfg_alias");
  if (m) m.value = ltNormalizeMac(mac);
  if (a) a.value = alias;
}

function ltSendTagConfig(mac, alias){
  ltSendDeviceConfig(mac, alias, $("tag_cfg_out"));
}

async function ltTagsSendConfig(ev){
  if (ev && ev.preventDefault) ev.preventDefault();
  const mac_raw = ( $("tag_cfg_mac") ? $("tag_cfg_mac").value : "" ).trim();
  const mac = ltNormalizeMac(mac_raw);
  const out = $("tag_cfg_out");
  if (!mac_raw){ alert("MAC fehlt"); return; }
  if (!mac){ alert("MAC-Format ungültig"); return; }
  const alias = ( $("tag_cfg_alias") ? $("tag_cfg_alias").value : "" ).trim();
  ltSendDeviceConfig(mac, alias, out);
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
  if (!r.ok || !r.json){
    if (out) out.textContent = `Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}`;
    const body = $("settings_tbody");
    if (body) body.innerHTML = `<tr><td colspan="3">Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}</td></tr>`;
    return;
  }
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);

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

// ---------------- OFL Fixture Library ----------------
let OFL_FIX_CACHE = [];
let OFL_PATCH_CACHE = [];

async function ltOflUpload(ev){
  ev.preventDefault();
  if (!await ltAssertNotLive("OFL Fixture Upload")) return;
  const fileInput = $("ofl_file");
  if (!fileInput || !fileInput.files.length){
    alert("Bitte JSON wählen.");
    return;
  }
  const out = $("ofl_upload_out");
  if (out) out.textContent = "uploading…";

  const form = new FormData();
  form.append("file", fileInput.files[0]);
  const mfr = $("ofl_mfr") ? $("ofl_mfr").value.trim() : "";
  const mdl = $("ofl_model") ? $("ofl_model").value.trim() : "";
  if (mfr) form.append("manufacturer", mfr);
  if (mdl) form.append("model", mdl);

  try{
    const r = await fetch(LT_API.oflImport, { method: "POST", body: form });
    let j = null;
    try { j = await r.json(); } catch (e) {}
    if (out) out.textContent = JSON.stringify(j || { status: r.status }, null, 2);
    if (r.ok){
      ltOflLoadFixtures();
      ltOflLoadPatches();
    }
  }catch(e){
    if (out) out.textContent = String(e);
  }
}

async function ltOflLoadFixtures(){
  const sel = $("ofl_sel_fixture") || $("patch_fixture");
  const table = $("ofl_library_tbody");
  if (sel) sel.innerHTML = `<option>lade…</option>`;
  if (table) table.innerHTML = `<tr><td colspan="4" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.oflFixtures);
  if (!r.ok || !r.json){
    if (sel) sel.innerHTML = `<option>Fehler</option>`;
    if (table) table.innerHTML = `<tr><td colspan="4">Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}</td></tr>`;
    return;
  }
  OFL_FIX_CACHE = r.json.fixtures || [];
  if (sel){
    if (!OFL_FIX_CACHE.length){
      sel.innerHTML = `<option value="">Keine Fixtures</option>`;
    }else{
      sel.innerHTML = OFL_FIX_CACHE.map(f => `<option value="${f.id}">${escapeHtml(f.manufacturer)} – ${escapeHtml(f.model)}</option>`).join("\n");
    }
  }
  ltOflOnFixtureSelect();
  if (table){
    if (!OFL_FIX_CACHE.length){
      table.innerHTML = `<tr><td colspan="4" class="muted">Keine Fixtures.</td></tr>`;
    }else{
      table.innerHTML = OFL_FIX_CACHE.map(f => {
        const modes = (f.modes || []).map(m => `${escapeHtml(m.name)} (${m.channels}ch)`).join(", ");
        return `<tr><td>${f.id}</td><td>${escapeHtml(f.manufacturer)}</td><td>${escapeHtml(f.model)}</td><td>${modes || "—"}</td></tr>`;
      }).join("\n");
    }
  }
}

function ltOflOnFixtureSelect(){
  const sel = $("ofl_sel_fixture") || $("patch_fixture");
  const modeSel = $("ofl_sel_mode") || $("patch_mode");
  if (!modeSel) return;
  const fid = Number(sel ? sel.value : 0);
  const fx = OFL_FIX_CACHE.find(f => f.id === fid);
  const modes = (fx && fx.modes) ? fx.modes : [];
  modeSel.innerHTML = modes.length ? modes.map(m => `<option value="${m.name}">${escapeHtml(m.name)} (${m.channels}ch)</option>`).join("\n") : `<option value="">Keine Modes</option>`;
  const nameField = $("ofl_name") || $("patch_name");
  if (nameField && fx && !nameField.value){
    nameField.value = `${fx.manufacturer} ${fx.model}`.trim();
  }
}

async function ltOflCreatePatch(){
  if (!await ltAssertNotLive("Patch Fixture")) return;
  const out = $("ofl_patch_out");
  if (out) out.textContent = "saving…";
  const payload = {
    fixture_id: Number((($("ofl_sel_fixture") || $("patch_fixture")) ? ($("ofl_sel_fixture") || $("patch_fixture")).value : 0)),
    name: ($("ofl_name") ? $("ofl_name").value : "") || ($("patch_name") ? $("patch_name").value : ""),
    mode_name: ($("ofl_sel_mode") ? $("ofl_sel_mode").value : "") || ($("patch_mode") ? $("patch_mode").value : ""),
    universe: Number(($("ofl_uni") ? $("ofl_uni").value : "") || ($("patch_uni") ? $("patch_uni").value : 0)),
    dmx_address: Number(($("ofl_addr") ? $("ofl_addr").value : "") || ($("patch_addr") ? $("patch_addr").value : 1)),
  };
  const r = await ltFetchJson(LT_API.oflPatchedFixtures, { method: "POST", body: JSON.stringify(payload) });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
  if (r.ok){
    ltOflLoadActiveTable();
  }
}

async function ltOflLoadActiveTable(){
  const body = $("ofl_active_tbody");
  if (!body) return;
  body.innerHTML = `<tr><td colspan="8" class="muted">lade…</td></tr>`;
  const r = await ltFetchJson(LT_API.oflPatchedFixtures);
  if (!r.ok || !r.json){
    body.innerHTML = `<tr><td colspan="8">Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}</td></tr>`;
    return;
  }
  const list = r.json.patched_fixtures || [];
  OFL_PATCH_CACHE = list;
  if (!list.length){
    body.innerHTML = `<tr><td colspan="8" class="muted">Keine aktiven Fixtures.</td></tr>`;
    return;
  }
  body.innerHTML = list.map(p => {
    const fx = p.fixture || {};
    return `<tr>
      <td>${p.id}</td>
      <td>${escapeHtml(p.name)}</td>
      <td>${escapeHtml(fx.manufacturer || '?')} – ${escapeHtml(fx.model || '?')}</td>
      <td>${escapeHtml(p.mode_name)}</td>
      <td>${escapeHtml(String(p.universe))}</td>
      <td>${escapeHtml(String(p.dmx_address))}</td>
      <td class="row"><button class="btn" onclick="ltOflTest(${p.id}, true)">Light ON</button><button class="btn" onclick="ltOflTest(${p.id}, false)">Light OFF</button></td>
      <td><a class="btn" href="/ui/patch/${p.id}/edit">Edit</a></td>
    </tr>`;
  }).join("\n");
}

async function ltOflTest(id, on){
  const out = $("ofl_patch_out");
  if (out) out.textContent = "testing…";
  const url = on ? LT_API.oflTestOn(id) : LT_API.oflTestOff(id);
  const r = await ltFetchJson(url, { method: "POST" });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
}

async function ltOflLoadPatchForEdit(id){
  const out = $("ofl_patch_out");
  if (out) out.textContent = "lade Patch…";
  const r = await ltFetchJson(LT_API.oflPatchedFixture(id));
  if (!r.ok || !r.json){
    if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
    return;
  }
  const patch = r.json.patch;
  if (out) out.textContent = "";
  // ensure fixtures loaded
  if (!OFL_FIX_CACHE.length){
    await ltOflLoadFixtures();
  }
  const selFx = $("ofl_sel_fixture");
  const selMode = $("ofl_sel_mode");
  if (selFx){
    selFx.value = patch.fixture_id;
  }
  ltOflOnFixtureSelect();
  if (selMode){
    selMode.value = patch.mode_name;
  }
  if ($("ofl_name")) $("ofl_name").value = patch.name || "";
  if ($("ofl_uni")) $("ofl_uni").value = patch.universe;
  if ($("ofl_addr")) $("ofl_addr").value = patch.dmx_address;
}

async function ltOflUpdatePatch(id){
  if (!await ltAssertNotLive("Patch Update")) return;
  const out = $("ofl_patch_out");
  if (out) out.textContent = "saving…";
  const payload = {
    fixture_id: Number($("ofl_sel_fixture") ? $("ofl_sel_fixture").value : 0),
    name: $("ofl_name") ? $("ofl_name").value : "",
    mode_name: $("ofl_sel_mode") ? $("ofl_sel_mode").value : "",
    universe: Number($("ofl_uni") ? $("ofl_uni").value : 0),
    dmx_address: Number($("ofl_addr") ? $("ofl_addr").value : 1),
  };
  const r = await ltFetchJson(LT_API.oflPatchedFixture(id), { method: "PUT", body: JSON.stringify(payload) });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
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
  if (!r.ok || !r.json){
    if (out) out.textContent = `Fehler: ${escapeHtml(JSON.stringify((r.json || r)))}`;
    return;
  }
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);

  const cfg = r.json.config || {};
  if (modeEl) modeEl.value = cfg.mode || "uart";
  if (uartEl) uartEl.value = cfg.uart_device || "/dev/serial0";
  if (tgtEl) tgtEl.value = cfg.artnet_target || "255.255.255.255";
  if (portEl) portEl.value = nz(cfg.artnet_port, 6454);
  if (uniEl) uniEl.value = nz(cfg.artnet_universe, 0);
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
    mode: $("dmx_mode") ? $("dmx_mode").value || "uart" : "uart",
    uart_device: $("dmx_uart_device") ? $("dmx_uart_device").value || undefined : undefined,
    artnet_target: $("artnet_target") ? $("artnet_target").value || undefined : undefined,
    artnet_port: asNumberOrNull($("artnet_port") ? $("artnet_port").value : undefined, 6454),
    artnet_universe: asNumberOrNull($("artnet_universe") ? $("artnet_universe").value : undefined, 0),
  };

  const r = await ltFetchJson(LT_API.dmxConfig, { method: "PUT", body: JSON.stringify(payload) });
  if (out) out.textContent = JSON.stringify((r.json || r), null, 2);
}

// Expose to window
window.ltRefreshFooterState = ltRefreshFooterState;
window.ltRefreshDashboard = ltRefreshDashboard;

window.ltSetAnchorPosition = ltSetAnchorPosition;
window.ltLoadSystemDefaults = ltLoadSystemDefaults;
window.ltSaveSystemDefaults = ltSaveSystemDefaults;
window.ltLoadWifiDefaults = ltLoadSystemDefaults;

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
window.ltOflUpload = ltOflUpload;
window.ltOflLoadFixtures = ltOflLoadFixtures;
window.ltOflOnFixtureSelect = ltOflOnFixtureSelect;
window.ltOflCreatePatch = ltOflCreatePatch;
window.ltOflTest = ltOflTest;
window.ltOflLoadPatchForEdit = ltOflLoadPatchForEdit;
window.ltOflUpdatePatch = ltOflUpdatePatch;
