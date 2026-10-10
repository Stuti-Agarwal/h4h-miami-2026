
const $ = (id) => document.getElementById(id);
const DEMO = { from: [25.77091, -80.19785], to: [25.80244, -80.20199] };
const map = L.map('map', { zoomControl: false }).setView([25.787, -80.197], 15);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> (ODbL) · Overture Maps · Miami-Dade County', maxZoom: 19,
}).addTo(map);
const shadowLayer = L.geoJSON(null, { style: { color: '#3c4043', weight: 0, fillOpacity: 0.16 }, interactive: false }).addTo(map);
const routeLayer = L.layerGroup().addTo(map);
const pin = (color) => L.divIcon({ className: '', iconSize: [28, 36], iconAnchor: [14, 34],
  html: `<svg width="28" height="36" viewBox="0 0 12 16"><path d="M6 0C2.7 0 0 2.6 0 5.8 0 10 6 16 6 16s6-6 6-10.2C12 2.6 9.3 0 6 0z" fill="${color}"/><circle cx="6" cy="6" r="2.2" fill="#fff"/></svg>` });
const SHIELD = (w, fill) => `<svg width="${w}" height="${w}" viewBox="0 0 24 24" aria-hidden="true" style="vertical-align:-2px"><path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5z" fill="${fill}"/></svg>`;
const SAFE_ICON = L.divIcon({ className: '', iconSize: [22, 22], iconAnchor: [11, 11],
  html: `<svg width="22" height="22" viewBox="0 0 22 22"><circle cx="11" cy="11" r="10" fill="#188038" stroke="#fff" stroke-width="1.5"/><path d="M11 4.5l5 1.9v3.8c0 3.1-2.1 5.9-5 6.9-2.9-1-5-3.8-5-6.9V6.4z" fill="#fff"/><path d="M11 7.5v5M8.5 10h5" stroke="#188038" stroke-width="1.6" stroke-linecap="round"/></svg>` });
const startPin = L.marker(DEMO.from, { draggable: true, icon: pin('#1a73e8'), title: 'Start (drag to move)' }).addTo(map);
const endPin = L.marker(DEMO.to, { draggable: true, icon: pin('#ea4335'), title: 'Destination (drag to move)' }).addTo(map);
let transitMode = false, custom = false, goal = 'auto', lang = 'English', last = null, selected = null, ticket = 0, history = [];

const fmtHour = (h) => { const hh = Math.floor(h), mm = Math.round((h % 1) * 60); return `${(hh % 12) || 12}:${String(mm).padStart(2, '0')} ${hh < 12 ? 'AM' : 'PM'}`; };
// US units for display; the API stays metric.
const km = (m) => (m / 1609.344).toFixed(1) + ' mi';
const ft = (m) => Math.round(m * 3.28084 / 10) * 10 + ' ft';
const perMi = (perKm) => (perKm * 1.609344).toFixed(1);
const mins = (m) => Math.round(m / 80) + ' min';  // ~4.8 km/h walking
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
function toast(text) { const t = $('toast'); t.textContent = text; t.style.display = 'block'; clearTimeout(toast.t); toast.t = setTimeout(() => t.style.display = 'none', 4000); }
function params() {
  const p = new URLSearchParams({ hour: $('hour').value, date: '2026-10-10', lang, goal, mode: transitMode ? 'transit' : 'walk' });
  if (custom) { const a = startPin.getLatLng(), b = endPin.getLatLng(); p.set('from', `${a.lng},${a.lat}`); p.set('to', `${b.lng},${b.lat}`); }
  return p;
}
async function getJSON(url, opts) {
  const r = await fetch(url, opts); const body = await r.json();
  if (!r.ok) throw new Error(body.error || 'Something went wrong');
  return body;
}

function draw() {
  routeLayer.clearLayers();
  const day = last.daylight, focus = selected || last.recommended;
  for (const r of [...last.routes].reverse()) {
    const pts = r.geometry.coordinates.map(([x, y]) => [y, x]);
    if (r.name !== focus) {
      if (nav) continue;  // walking view: only the chosen route
      L.polyline(pts, { color: '#bdc1c6', weight: 7, opacity: .9 }).on('click', () => { selected = r.name; render(); }).addTo(routeLayer);
      continue;
    }
    L.polyline(pts, { color: '#174ea6', weight: 10, opacity: 1, interactive: false }).addTo(routeLayer);
    const s = r.samples;
    for (let i = 1; i < s.length; i++) {
      const good = day ? s[i].shaded : (s[i].lit || s[i].active);
      L.polyline([[s[i - 1].lat, s[i - 1].lon], [s[i].lat, s[i].lon]],
        { color: good ? (day ? '#1a73e8' : '#fdd663') : (day ? '#f9ab00' : '#3c4043'), weight: 6, opacity: 1, interactive: false }).addTo(routeLayer);
    }
    // Under I-95/I-395: dashed grey on top so the overpass stretches stand out.
    for (let i = 1; i < s.length; i++) {
      if (s[i].under) L.polyline([[s[i - 1].lat, s[i - 1].lon], [s[i].lat, s[i].lon]],
        { color: '#5f6368', weight: 4, opacity: 1, dashArray: '4 6', interactive: false }).addTo(routeLayer);
    }
    // Transit legs (mode=transit): dashed purple on top of the walk colouring.
    for (const l of r.legs || []) {
      if (l.type !== 'transit' || !l.geometry || !Array.isArray(l.geometry.coordinates)) continue;
      L.polyline(l.geometry.coordinates.map(([x, y]) => [y, x]), { color: '#9334e6', weight: 6, opacity: 1, dashArray: '10 8', interactive: false }).addTo(routeLayer);
    }
    // Places to step inside along this route (markers sit in the marker pane, above the lines).
    for (const st of r.safe_stops || []) {
      const label = `${st.name} · ${String(st.category).replace(/_/g, ' ')}`;
      L.marker([st.lat, st.lon], { icon: SAFE_ICON, title: label, alt: label })
        .bindTooltip(esc(label), { direction: 'top', offset: [0, -10] })
        .bindPopup(esc(st.name)).addTo(routeLayer);
    }
  }
}

// "Walk 0.3 mi → Metromover Omni Loop from X to Y 1.1 mi → Walk 0.4 mi"; '' when the backend sent no legs.
const legsText = (r) => Array.isArray(r.legs) && r.legs.length ? r.legs.map((l) => l.type === 'transit'
  ? [l.line || 'Transit', l.from && `from ${l.from}`, l.to && `to ${l.to}`, l.distance_m != null && km(l.distance_m)].filter(Boolean).join(' ')
  : `Walk${l.distance_m != null ? ' ' + km(l.distance_m) : ''}`).join(' → ') : '';
function render() {
  const day = last.daylight;
  document.body.classList.toggle('night', !day);
  // Transit mode with real legs from the backend: show route cards instead of the stops-only board.
  document.body.classList.toggle('legs', transitMode && last.routes.some((r) => Array.isArray(r.legs) && r.legs.length));
  const busy = (last.goal || goal) === 'busy';  // server ranks by busy streets after dark even in auto
  $('mode').textContent = busy ? 'Busy streets · storefronts + traffic' : day ? 'Day · least sun' : 'Night · lit & busy';
  $('goalchip').textContent = day ? 'Shadiest' : 'Busy & lit';
  $('chatctx').textContent = `Gemma 4 · ${busy ? 'Busiest · ' : ''}${last.recommended} · ${fmtHour(+$('hour').value)}`;
  // Same busy score the server ranks by (storefronts x10 + cars/day / 100), so the winner has the fullest bar.
  const busyScore = (r) => (+r.storefronts_per_km || 0) * 10 + (+r.traffic_aadt || 0) / 100;
  const maxSf = Math.max(0, ...last.routes.map(busyScore));
  $('routes').innerHTML = last.routes.map((r) => {
    const best = r.name === last.recommended, mine = r.name === (selected || last.recommended);
    const good = busy ? (maxSf ? busyScore(r) / maxSf : 0) : day ? r.shade : 1 - r.longest_dark_m / r.distance_m;
    const busyText = [typeof r.storefronts_per_km === 'number' ? `${perMi(r.storefronts_per_km)} storefronts/mi` : '',
                      typeof r.traffic_aadt === 'number' ? `~${(Math.round(r.traffic_aadt / 100) * 100).toLocaleString()} cars/day` : ''].filter(Boolean).join(' · ');
    const detail = (busy ? busyText || 'Busy-street data loading' : day ? `${km(r.sun_exposed_m)} in direct sun · ${Math.round(r.shade * 100)}% shaded`
                        : `Longest dark stretch ${ft(r.longest_dark_m)} · ${Math.round(r.lit * 100)}% lit`)
                   + (r.under_highway_m ? ` · ${ft(r.under_highway_m)} under highways` : '');
    const nStops = (r.safe_stops || []).length;
    const safety = [nStops ? `${nStops} safe stop${nStops === 1 ? '' : 's'}` : '',
                    typeof r.incidents_per_km === 'number' ? `${perMi(r.incidents_per_km)} police reports/mi nearby` : ''].filter(Boolean).join(' · ');
    return `<button class="route ${best ? 'best' : ''}" data-name="${esc(r.name)}" style="${mine && !best ? 'border-color:#202124' : ''}">
      <span class="top"><span>${esc(r.name)}</span>${best ? `<span class="badge">${busy ? 'Busiest' : day ? 'Shadiest' : 'Brightest'}</span>` : `<span class="sub">${mins(r.distance_m)}</span>`}</span>
      <span class="sub">${best ? `<b style="color:#188038">${mins(r.distance_m)}</b> (${km(r.distance_m)}) · ` : `${km(r.distance_m)} · `}${detail}</span>
      ${safety ? `<span class="sub">${SHIELD(12, '#188038')} ${esc(safety)}</span>` : ''}
      ${legsText(r) ? `<span class="sub" style="color:#7627bb">${esc(legsText(r))}</span>` : ''}
      <span class="bar"><span style="width:${Math.round(good * 100)}%;background:${busy || day ? '#1a73e8' : '#fdd663'}"></span><span style="flex:1;background:${busy ? '#e8eaed' : day ? '#fde293' : '#5f6368'}"></span></span>
    </button>`;
  }).join('');
  document.querySelectorAll('.route').forEach((el) => el.onclick = () => { selected = el.dataset.name; render(); });
  const focus = last.routes.find((r) => r.name === (selected || last.recommended));
  $('gmaps').href = gmapsUrl(focus, transitMode);
  $('gmapslabel').textContent = transitMode ? 'Directions' : 'Maps';
  $('gmaps').setAttribute('aria-label', transitMode ? 'Transit directions in Google Maps' : `Walk ${focus.name} in Google Maps`);
  draw();
}

// Hand-off: Google Maps does turn-by-turn; a few waypoints along our pick keep it on the shady/bright path.
// ponytail: 3 evenly spaced waypoints (mobile Maps URLs allow only a few); pick turn points if it drifts.
function gmapsUrl(route, transit) {
  const c = route.geometry.coordinates, ll = ([x, y]) => `${y.toFixed(5)},${x.toFixed(5)}`;
  const via = [1, 2, 3].map((i) => ll(c[Math.round((c.length - 1) * i / 4)]));
  // Typed names read better in Maps than coordinates, which it snaps to whatever listing is nearest.
  const place = (id, pt) => $(id).value && $(id).value !== 'Dropped pin' ? `${$(id).value}, Miami, FL` : ll(pt);
  const q = { api: 1, origin: place('from', c[0]), destination: place('to', c[c.length - 1]), travelmode: transit ? 'transit' : 'walking' };
  if (!transit) q.waypoints = via.join('|');
  return 'https://www.google.com/maps/dir/?' + new URLSearchParams(q);
}

async function update(fit) {
  $('clock').textContent = fmtHour(+$('hour').value);
  const my = ++ticket, p = params();
  try {
    const [routes, shadows] = await Promise.all([getJSON('/api/routes?' + p), getJSON('/api/shadows?' + p)]);
    if (my !== ticket) return;  // a newer request is already in flight
    last = routes; if (fit) selected = null;
    shadowLayer.clearLayers().addData(shadows);
    render();
    if (fit) map.fitBounds(L.latLngBounds(routes.routes.flatMap((r) => r.geometry.coordinates.map(([x, y]) => [y, x]))),
      window.innerWidth >= 760 ? { paddingTopLeft: [440, 40], paddingBottomRight: [40, 40] } : { paddingTopLeft: [20, 170], paddingBottomRight: [20, window.innerHeight * .5] });
    loadSummary(my);
    if (transitMode) loadTransit();
  } catch (e) { if (my === ticket) toast(e.message); }
}

async function loadSummary(my) {
  $('summary').className = 'loading'; $('summary').textContent = 'Thinking about your walk…'; $('engine').textContent = '';
  try {
    const s = await getJSON('/api/summary?' + params());
    if (my !== ticket) return;
    $('summary').className = ''; $('summary').textContent = s.text;
    $('engine').textContent = s.engine === 'none' ? '' : `via ${s.engine}`;
  } catch (e) { if (my === ticket) $('summary').textContent = e.message; }
}

async function place(input, marker) {
  try {
    const hit = await getJSON('/api/geocode?q=' + encodeURIComponent(input.value));
    marker.setLatLng([hit.lat, hit.lon]); input.value = hit.label.split(',')[0];
    return true;
  } catch (e) { toast(e.message); return false; }
}

// Inputs whose value matches their pin (demo defaults, a picked suggestion, a geocode or a dropped pin).
const chosen = { from: true, to: true };
$('trip').addEventListener('submit', async (e) => {
  e.preventDefault(); document.activeElement.blur();
  if ((chosen.from || await place($('from'), startPin)) && (chosen.to || await place($('to'), endPin))) {
    chosen.from = chosen.to = true; custom = true; update(true);
  }
});

// Type-ahead suggestions (Google Maps style). Rows are built with textContent only: labels come from third-party data.
const sugg = $('sugg'), PIN_SVG = 'M6 0C2.7 0 0 2.6 0 5.8 0 10 6 16 6 16s6-6 6-10.2C12 2.6 9.3 0 6 0z';
let suggFor = null, suggItems = [], suggIdx = -1, suggSeq = 0, suggTimer, blurTimer;
function closeSugg() {
  sugg.hidden = true; sugg.replaceChildren(); suggItems = []; suggIdx = -1;
  for (const id of ['from', 'to']) { $(id).setAttribute('aria-expanded', 'false'); $(id).removeAttribute('aria-activedescendant'); }
}
function highlight(i) {
  suggIdx = i;
  [...sugg.children].forEach((li, j) => li.setAttribute('aria-selected', String(j === i)));
  if (i >= 0) { sugg.children[i].scrollIntoView({ block: 'nearest' }); suggFor.setAttribute('aria-activedescendant', sugg.children[i].id); }
  else suggFor.removeAttribute('aria-activedescendant');
}
function pick(i) {
  const s = suggItems[i], input = suggFor; if (!s) return;
  input.value = s.label; (input.id === 'from' ? startPin : endPin).setLatLng([s.lat, s.lon]);
  chosen[input.id] = true; custom = true; closeSugg();
  if (chosen.from && chosen.to) { input.blur(); update(true); }
  else $(input.id === 'from' ? 'to' : 'from').focus();
}
function showSugg(input, items) {
  closeSugg(); if (!items.length || document.activeElement !== input) return;
  suggFor = input; suggItems = items;
  items.forEach((s, i) => {
    const li = document.createElement('li'); li.id = 'sugg-' + i; li.setAttribute('role', 'option'); li.setAttribute('aria-selected', 'false');
    const ic = document.createElement('span'); ic.className = 'ic';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); svg.setAttribute('width', '12'); svg.setAttribute('height', '16'); svg.setAttribute('viewBox', '0 0 12 16'); svg.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path'); path.setAttribute('d', PIN_SVG); path.setAttribute('fill', '#5f6368');
    svg.appendChild(path); ic.appendChild(svg);
    const tx = document.createElement('span'); tx.className = 'tx';
    const b = document.createElement('b'); b.textContent = s.label; tx.appendChild(b);
    if (s.detail) { const sm = document.createElement('small'); sm.textContent = s.detail; tx.appendChild(sm); }
    li.append(ic, tx);
    li.addEventListener('mousedown', (e) => e.preventDefault());  // keep focus in the input so blur doesn't close first
    li.addEventListener('click', () => pick(i));
    sugg.appendChild(li);
  });
  sugg.hidden = false; input.setAttribute('aria-expanded', 'true');
}
for (const id of ['from', 'to']) {
  const input = $(id);
  input.addEventListener('input', () => {
    chosen[id] = false; clearTimeout(suggTimer);
    const q = input.value.trim(), my = ++suggSeq;
    if (q.length < 2) { closeSugg(); return; }
    suggTimer = setTimeout(async () => {
      // Local matches render instantly; the full list (with street addresses) replaces them when it arrives.
      const url = '/api/suggest?q=' + encodeURIComponent(q);
      getJSON(url + '&remote=0').then((items) => { if (my === suggSeq && items.length) showSugg(input, items); }).catch(() => {});
      try { const items = await getJSON(url); if (my === suggSeq) showSugg(input, items); }
      catch (e) { if (my === suggSeq && sugg.hidden) closeSugg(); }
    }, 120);
  });
  input.addEventListener('keydown', (e) => {
    if (sugg.hidden || suggFor !== input) return;
    const n = suggItems.length;
    if (e.key === 'ArrowDown') { e.preventDefault(); highlight((suggIdx + 1) % n); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); highlight(suggIdx <= 0 ? n - 1 : suggIdx - 1); }
    else if (e.key === 'Escape') { e.preventDefault(); closeSugg(); }
    else if (e.key === 'Enter') { if (suggIdx >= 0) { e.preventDefault(); pick(suggIdx); } else closeSugg(); }
  });
  input.addEventListener('blur', () => { clearTimeout(blurTimer); blurTimer = setTimeout(() => { const f = document.activeElement; if (f !== $('from') && f !== $('to')) { ++suggSeq; closeSugg(); } else if (f !== input && suggFor === input) closeSugg(); }, 150); });
}
$('swap').onclick = () => {
  const a = startPin.getLatLng(), b = endPin.getLatLng(); startPin.setLatLng(b); endPin.setLatLng(a);
  [$('from').value, $('to').value] = [$('to').value, $('from').value]; [chosen.from, chosen.to] = [chosen.to, chosen.from]; custom = true; update(true);
};
for (const [m, input] of [[startPin, 'from'], [endPin, 'to']]) {
  m.on('dragend', () => { custom = true; $(input).value = 'Dropped pin'; chosen[input] = true; update(true); });
}
let t;
$('hour').addEventListener('input', () => { $('clock').textContent = fmtHour(+$('hour').value); clearTimeout(t); t = setTimeout(() => update(false), 200); });
document.querySelectorAll('.goal').forEach((b) => b.onclick = () => {
  if (goal === b.dataset.goal) return;
  goal = b.dataset.goal; document.querySelectorAll('.goal').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); update(true);
});
document.querySelectorAll('.lang').forEach((b) => b.onclick = () => {
  lang = b.dataset.lang; document.querySelectorAll('.lang').forEach((x) => x.classList.toggle('on', x === b)); loadSummary(ticket);
});

function addMsg(role, text, engine) {
  const d = document.createElement('div'); d.className = 'msg ' + role; d.textContent = text;
  if (engine) { const s = document.createElement('small'); s.textContent = 'via ' + engine; d.appendChild(s); }
  $('msgs').appendChild(d); $('msgs').scrollTop = 1e9; return d;
}
async function ask(q) {
  if (!q.trim()) return;
  addMsg('user', q); const wait = addMsg('gemma', '…');
  try {
    const a = await getJSON('/api/chat', { method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ...Object.fromEntries(params()), question: q, history }) });
    wait.remove(); addMsg('gemma', a.text, a.engine);
    history.push({ role: 'user', text: q }, { role: 'gemma', text: a.text });
  } catch (e) { wait.textContent = e.message; }
}
$('openchat').onclick = () => {
  $('chat').classList.add('open');
  if (!$('msgs').children.length) addMsg('gemma', 'Hi! Ask me anything about these routes: shade, lighting, places to stop or when to leave.');
  $('q').focus();
};
async function shareText(text, url) {
  try {
    if (navigator.share) { await navigator.share({ title: 'SombraRoute trip', text, url }); return; }
    await navigator.clipboard.writeText(text + ' ' + url); toast('Trip copied — paste it to a friend');
  } catch (e) { if (e.name !== 'AbortError') toast('Could not share — try again'); }  // AbortError = user cancelled the share sheet
}
$('share').onclick = () => {
  if (!last) return;
  const focus = last.routes.find((r) => r.name === (selected || last.recommended)), url = gmapsUrl(focus);
  shareText(`I'm walking from ${$('from').value} to ${$('to').value} via ${focus.name}, leaving ${fmtHour(+$('hour').value)}, about ${mins(focus.distance_m)}. Route:`, url);
};
const near = () => $('from').value.trim() || 'your start point';
function closeSos() { $('sospanel').hidden = true; $('sos').focus(); }
$('sos').onclick = () => { $('sosnear').textContent = near(); $('sospanel').hidden = false; $('sospanel').querySelector('.call').focus(); };
$('soscancel').onclick = closeSos;
$('sosshare').onclick = () => {
  const a = startPin.getLatLng();
  shareText(`I need help. I'm near ${near()}.`, `https://www.google.com/maps/search/?api=1&query=${a.lat.toFixed(5)},${a.lng.toFixed(5)}`);
};
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !$('sospanel').hidden) closeSos(); });
$('closechat').onclick = () => $('chat').classList.remove('open');
$('compose').addEventListener('submit', (e) => { e.preventDefault(); const q = $('q').value; $('q').value = ''; ask(q); });
document.querySelectorAll('.suggest button').forEach((b) => b.onclick = () => ask(b.dataset.q));

// ---- Transit: nearby stops at each end (no re-ranking) ----
const transitLayer = L.layerGroup().addTo(map);
const TRANSIT_ICON = {
  bus: '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="3" width="14" height="15" rx="3" fill="none" stroke="#1967d2" stroke-width="2"/><path d="M5 11h14M8 21l1-3M16 21l-1-3" stroke="#1967d2" stroke-width="2" stroke-linecap="round"/></svg>',
  train: '<svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="2" width="12" height="15" rx="4" fill="none" stroke="#1967d2" stroke-width="2"/><circle cx="9.5" cy="13" r="1.3" fill="#1967d2"/><circle cx="14.5" cy="13" r="1.3" fill="#1967d2"/><path d="M6 8h12M8 22l2-4M16 22l-2-4" stroke="#1967d2" stroke-width="2" stroke-linecap="round"/></svg>',
};
let transitSeq = 0;
function transitList(title, stops) {
  const box = document.createElement('div'), h = document.createElement('h3'), ul = document.createElement('ul');
  h.textContent = title; box.append(h, ul);
  if (!stops.length) { const li = document.createElement('li'); li.className = 'sub'; li.textContent = 'No stops within walking distance'; ul.appendChild(li); }
  for (const s of stops) {
    const li = document.createElement('li'), ic = document.createElement('span'), tx = document.createElement('span'), b = document.createElement('b'), w = document.createElement('span');
    ic.className = 'ic'; ic.innerHTML = s.kind === 'bus' ? TRANSIT_ICON.bus : TRANSIT_ICON.train;  // static SVG only
    tx.className = 'tx'; b.style.fontWeight = '500'; b.textContent = s.name; tx.appendChild(b);
    const routes = Array.isArray(s.routes) ? s.routes.join(', ') : (s.routes || '');
    const kind = s.kind === 'bus' ? 'Bus' : s.kind === 'metromover' ? 'Metromover' : 'Metrorail';
    const sm = document.createElement('small'); sm.className = 'sub'; sm.textContent = routes ? `${kind} · ${routes}` : kind; tx.appendChild(sm);
    w.className = 'walk'; w.textContent = `${ft(s.walk_m)} walk`;
    li.append(ic, tx, w); ul.appendChild(li);
    L.circleMarker([s.lat, s.lon], { radius: 6, color: '#fff', weight: 2, fillColor: '#1a73e8', fillOpacity: 1 })
      .bindTooltip(esc(`${s.name}${routes ? ' · ' + routes : ''}`), { direction: 'top' }).addTo(transitLayer);
  }
  return box;
}
async function loadTransit() {
  const my = ++transitSeq, p = new URLSearchParams();
  if (custom) { const a = startPin.getLatLng(), b = endPin.getLatLng(); p.set('from', `${a.lng},${a.lat}`); p.set('to', `${b.lng},${b.lat}`); }
  const box = $('transit'), note = document.createElement('p');
  note.className = 'sub'; note.style.margin = '0'; note.textContent = 'Finding stops…'; box.replaceChildren(note);
  try {
    const res = await fetch('/api/transit' + (custom ? '?' + p : ''));
    const body = await res.json().catch(() => ({}));
    if (!res.ok || !Array.isArray(body.board)) throw new Error(res.status === 400 && body.error ? body.error : 'Transit info unavailable');
    if (my !== transitSeq || !transitMode) return;
    transitLayer.clearLayers();
    box.replaceChildren(transitList('Board near start', body.board), transitList('Get off near destination', body.alight || []));
  } catch (e) {
    if (my !== transitSeq) return;
    const msg = e instanceof TypeError ? 'Transit info unavailable' : e.message;
    toast(msg); note.textContent = msg;
  }
}
function setTransit(on) {
  transitMode = on;
  $('walkchip').setAttribute('aria-pressed', String(!on)); $('transitchip').setAttribute('aria-pressed', String(on));
  document.body.classList.toggle('transit', on);
  transitLayer.clearLayers(); ++transitSeq;
  if (last) update(true);  // re-fetch routes/summary with the new mode (update loads transit stops too)
  else if (on) loadTransit();
}
$('walkchip').onclick = () => transitMode && setTransit(false);
$('transitchip').onclick = () => !transitMode && setTransit(true);

// ---- Start: follow-me walking view ----
const hav = (a, b) => {
  const R = 6371000, k = Math.PI / 180, dLat = (b[0] - a[0]) * k, dLon = (b[1] - a[1]) * k;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a[0] * k) * Math.cos(b[0] * k) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};
const meDot = L.marker([0, 0], { icon: L.divIcon({ className: '', iconSize: [18, 18], iconAnchor: [9, 9], html: '<div class="me"></div>' }), interactive: false, keyboard: false, zIndexOffset: 1000 });
const meAcc = L.circle([0, 0], { radius: 0, color: '#1a73e8', weight: 1, fillColor: '#1a73e8', fillOpacity: .12, interactive: false });
let nav = null;
const nearestIdx = (ll) => { let bi = 0, bd = Infinity; nav.pts.forEach((p, i) => { const d = hav(ll, p); if (d < bd) { bd = d; bi = i; } }); return [bi, bd]; };
function showProgress(ll, along) {
  meDot.setLatLng(ll).addTo(map);
  const left = Math.max(0, nav.total - along);
  $('navleft').textContent = left < 15 ? 'Arrived' : `${km(left)} · ${mins(left)}`;
  const next = nav.stops.find((s) => s.along >= along);
  $('navstop').textContent = next ? `Next safe stop: ${next.name} · ${next.along - along >= 300 ? km(next.along - along) : ft(next.along - along)}` : '';
  if (nav.follow) map.panTo(ll, { animate: true });
}
function startPreview(why) {
  if (nav.timer) return;
  meAcc.remove(); $('navnote').textContent = why;
  const t0 = performance.now();
  nav.timer = setInterval(() => {
    const along = nav.total * Math.min(1, ((performance.now() - t0) / 30000));
    let i = 1; while (i < nav.cum.length - 1 && nav.cum[i] < along) i++;
    const seg = nav.cum[i] - nav.cum[i - 1] || 1, f = Math.min(1, Math.max(0, (along - nav.cum[i - 1]) / seg)), a = nav.pts[i - 1], b = nav.pts[i];
    showProgress([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f], along);
    if (along >= nav.total) { clearInterval(nav.timer); }
  }, 250);
}
function startNav() {
  if (!last) return;
  const r = last.routes.find((x) => x.name === (selected || last.recommended));
  const pts = r.geometry.coordinates.map(([x, y]) => [y, x]), cum = [0];
  for (let i = 1; i < pts.length; i++) cum.push(cum[i - 1] + hav(pts[i - 1], pts[i]));
  nav = { pts, cum, total: cum[cum.length - 1], follow: false, stops: [] };
  nav.stops = (r.safe_stops || []).map((s) => ({ name: s.name, along: cum[nearestIdx([s.lat, s.lon])[0]] })).sort((a, b) => a.along - b.along);
  document.body.classList.add('nav'); closeSugg();
  $('navname').textContent = r.name; $('navnote').textContent = 'Finding your location…';
  draw();  // hides the other routes
  map.fitBounds(L.latLngBounds(pts), window.innerWidth >= 760 ? { paddingTopLeft: [440, 40], paddingBottomRight: [40, 40] } : { paddingTopLeft: [20, 40], paddingBottomRight: [20, 140] });
  showProgress(pts[0], 0);
  $('endnav').focus();
  if (!navigator.geolocation || !window.isSecureContext) { startPreview('GPS unavailable — preview'); return; }
  // No fix within a few seconds (desktop, denied, indoors) -> preview so the demo still moves.
  nav.wait = setTimeout(() => startPreview('GPS unavailable — preview'), 4000);
  nav.watch = navigator.geolocation.watchPosition((pos) => {
    if (!nav) return;
    const ll = [pos.coords.latitude, pos.coords.longitude], [i, off] = nearestIdx(ll);
    if (off > 1000) { clearTimeout(nav.wait); startPreview('You are away from this route — preview'); return; }
    clearTimeout(nav.wait); clearInterval(nav.timer); nav.timer = null;
    $('navnote').textContent = '';
    meAcc.setLatLng(ll).setRadius(pos.coords.accuracy || 0).addTo(map);
    showProgress(ll, cum[i]);
  }, () => { if (nav) { clearTimeout(nav.wait); startPreview('GPS unavailable — preview'); } }, { enableHighAccuracy: true, maximumAge: 5000 });
}
function endNav() {
  if (!nav) return;
  if (nav.watch != null) navigator.geolocation.clearWatch(nav.watch);
  clearTimeout(nav.wait); clearInterval(nav.timer); nav = null;
  meDot.remove(); meAcc.remove(); document.body.classList.remove('nav'); draw();
  map.fitBounds(L.latLngBounds(last.routes.flatMap((r) => r.geometry.coordinates.map(([x, y]) => [y, x]))),
    window.innerWidth >= 760 ? { paddingTopLeft: [440, 40], paddingBottomRight: [40, 40] } : { paddingTopLeft: [20, 170], paddingBottomRight: [20, window.innerHeight * .5] });
  $('start').focus();
}
map.on('dragstart', () => { if (nav) nav.follow = false; });
$('start').onclick = startNav;
$('endnav').onclick = endNav;

update(true);
