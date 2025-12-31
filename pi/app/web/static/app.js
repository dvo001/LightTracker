// Minimal LightTracker JS client
async function ltFetchJson(url, opts){
  try{
    const res = await fetch(url, opts);
    const json = await (res.headers.get('content-type')||'').includes('application/json') ? await res.json() : null;
    return { ok: res.ok, status: res.status, json };
  }catch(e){
    return { ok: false, status: 0, json: null };
  }
}

async function ltGetSystemState(){
  return await ltFetchJson('/api/v1/state');
}

async function ltAssertNotLive(actionName){
  const s = await ltGetSystemState();
  const state = s.json && s.json.system_state ? s.json.system_state : null;
  if(state === 'LIVE'){
    alert(actionName + ' is disabled while system is LIVE');
    return false;
  }
  return true;
}

// Auto-init: refresh dashboard if present
document.addEventListener('DOMContentLoaded', async ()=>{
  const d = document.getElementById('dashboard');
  if(d){
    const r = await ltGetSystemState();
    d.innerText = r.ok && r.json ? JSON.stringify(r.json) : 'Could not load state';
  }

  // Fixtures list
  if(document.getElementById('fixtures')){
    ltLoadFixtures();
  }

  // Fixture new form
  const newForm = document.getElementById('fixture-new-form');
  if(newForm){
    newForm.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      if(!(await ltAssertNotLive('Create fixture'))) return;
      const fd = new FormData(newForm);
      const body = { name: fd.get('name'), profile_key: fd.get('profile'), universe: parseInt(fd.get('universe')||1), dmx_base_addr: parseInt(fd.get('dmx_address')||1) };
      const r = await ltFetchJson('/api/v1/fixtures', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(r.ok){ location.href = '/ui/fixtures'; } else { alert('Failed to create fixture: ' + (r.json && r.json.detail ? JSON.stringify(r.json.detail) : r.status)); }
    });
  }

  // Fixture edit form
  const editForm = document.getElementById('fixture-edit-form');
  const fixtureIdElem = document.getElementById('fixture-id');
  if(editForm && fixtureIdElem){
    const fid = fixtureIdElem.dataset.id;
    // load fixture
    (async ()=>{
      const r = await ltFetchJson('/api/v1/fixtures/' + fid);
      if(r.ok && r.json){
        const f = r.json;
        editForm.elements['name'].value = f.name || '';
        editForm.elements['profile'].value = f.profile_key || '';
        editForm.elements['universe'].value = f.universe || '';
        editForm.elements['dmx_address'].value = f.dmx_base_addr || '';
      }
    })();

    editForm.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      if(!(await ltAssertNotLive('Save fixture'))) return;
      const fd = new FormData(editForm);
      const body = { name: fd.get('name'), profile_key: fd.get('profile'), universe: parseInt(fd.get('universe')||1), dmx_base_addr: parseInt(fd.get('dmx_address')||1) };
      const r = await ltFetchJson('/api/v1/fixtures/' + fid, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(r.ok){ location.href = '/ui/fixtures'; } else { alert('Failed to save fixture'); }
    });
  }

  // Anchors page: simple form handler (list not available in API)
  const anchorsDiv = document.getElementById('anchors');
  if(anchorsDiv){
    anchorsDiv.innerHTML = `
      <p>No anchor list endpoint available. You can set an anchor position below.</p>
      <form id="anchor-pos-form">
        <label>MAC <span class="req">*</span><input name="mac" required></label>
        <label>X (cm) <input name="x_cm" required type="number"></label>
        <label>Y (cm) <input name="y_cm" required type="number"></label>
        <label>Z (cm) <input name="z_cm" required type="number"></label>
        <button class="btn" type="submit">Set Position</button>
      </form>
    `;
    const apf = document.getElementById('anchor-pos-form');
    apf.addEventListener('submit', async (ev)=>{
      ev.preventDefault();
      if(!(await ltAssertNotLive('Set anchor position'))) return;
      const fd = new FormData(apf);
      const body = { mac: fd.get('mac'), x_cm: parseInt(fd.get('x_cm')||0), y_cm: parseInt(fd.get('y_cm')||0), z_cm: parseInt(fd.get('z_cm')||0) };
      const r = await ltFetchJson('/api/v1/anchors/position', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(body) });
      if(r.ok){ alert('Position set'); } else { alert('Failed to set position: ' + (r.json && r.json.detail ? JSON.stringify(r.json.detail) : r.status)); }
    });
  }
});



// Load fixtures list and render simple table with actions
async function ltLoadFixtures(){
  const div = document.getElementById('fixtures');
  if(!div) return;
  const r = await ltFetchJson('/api/v1/fixtures');
  if(!r.ok || !r.json){ div.innerText = 'Could not load fixtures'; return; }
  const list = r.json.fixtures || [];
  const table = document.createElement('table');
  table.className = 'fixtures-table';
  const thead = document.createElement('thead');
  thead.innerHTML = '<tr><th>ID</th><th>Name</th><th>Universe</th><th>DMX</th><th>Actions</th></tr>';
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  for(const f of list){
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${f.id}</td><td>${f.name||''}</td><td>${f.universe||''}</td><td>${f.dmx_base_addr||''}</td>`;
    const act = document.createElement('td');
    const edit = document.createElement('a'); edit.href = '/ui/fixtures/' + f.id + '/edit'; edit.className='btn'; edit.innerText='Edit';
    const del = document.createElement('button'); del.className='btn'; del.style.marginLeft='6px'; del.innerText='Delete';
    del.addEventListener('click', async ()=>{
      if(!(await ltAssertNotLive('Delete fixture'))) return;
      if(!confirm('Delete fixture '+f.id+'?')) return;
      const dr = await ltFetchJson('/api/v1/fixtures/' + f.id, { method: 'DELETE' });
      if(dr.ok) ltLoadFixtures(); else alert('Failed to delete');
    });
    act.appendChild(edit); act.appendChild(del);
    tr.appendChild(act);
    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  div.innerHTML = ''; div.appendChild(table);
}
