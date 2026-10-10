
(() => {
  const ob = document.getElementById('ob'), slides = [...ob.querySelectorAll('.ob-slide')];
  const dots = document.getElementById('obdots'), back = document.getElementById('obback'), next = document.getElementById('obnext');
  let i = 0, opener = null;
  const help = document.createElement('button');
  // Static, trusted strings (no user input), keyed by the main script's lang values.
  const OB = {
    English: { code: 'en', skip: 'Skip', back: 'Back', next: 'Next', done: 'Get started', help: 'How it works', step: (n, m) => `Step ${n} of ${m}`,
      t: ['Welcome to SombraRoute', 'How routes are ranked', 'Walk or ride', 'Ask Gemma'],
      b: ['<p>Find cooler, more comfortable walks between Downtown Miami and Wynwood. We compare a few routes and show you the one that fits the time of day.</p>',
        '<ul><li><b>Daytime:</b> more shade from buildings and trees</li><li><b>Evening:</b> well-lit streets with places open late</li><li><b>Busiest:</b> streets with storefronts and steady traffic</li><li>Fewer reported incidents along the way</li><li>Less walking under highway overpasses</li></ul>',
        '<p>Use the <b>Walk</b> and <b>Transit</b> chips to switch between walking the whole way or combining the free Metromover with short walks.</p><p style="margin-top:8px">Tap <b>Start</b> to follow your route live on the map.</p>',
        '<p>Gemma summarizes your options. Tap <b>Ask Gemma</b> to ask things like “Which route has more open places to stop?”</p><p style="margin-top:8px">Tap <b>EN</b>, <b>ES</b> (Español) or <b>KRE</b> (Kreyòl ayisyen) to change the language.</p>'] },
    Spanish: { code: 'es', skip: 'Omitir', back: 'Atrás', next: 'Siguiente', done: 'Empezar', help: 'Cómo funciona', step: (n, m) => `Paso ${n} de ${m}`,
      t: ['Bienvenido a SombraRoute', 'Cómo elegimos las rutas', 'Camina o viaja', 'Pregúntale a Gemma'],
      b: ['<p>Encuentra caminatas más frescas y cómodas entre Downtown Miami y Wynwood. Comparamos varias rutas y te mostramos la que mejor va con la hora del día.</p>',
        '<ul><li><b>De día:</b> más sombra de edificios y árboles</li><li><b>De noche:</b> calles bien iluminadas con lugares abiertos hasta tarde</li><li><b>Busiest:</b> calles con tiendas y movimiento constante</li><li>Menos incidentes reportados en el camino</li><li>Menos tramos bajo pasos elevados de autopista</li></ul>',
        '<p>Usa los botones <b>Walk</b> y <b>Transit</b> para caminar todo el trayecto o combinar el Metromover gratuito con caminatas cortas.</p><p style="margin-top:8px">Toca <b>Start</b> para seguir tu ruta en vivo en el mapa.</p>',
        '<p>Gemma resume tus opciones. Toca <b>Ask Gemma</b> para preguntar cosas como “¿Qué ruta tiene más lugares abiertos para parar?”</p><p style="margin-top:8px">Toca <b>EN</b>, <b>ES</b> (Español) o <b>KRE</b> (Kreyòl ayisyen) para cambiar el idioma.</p>'] },
    'Haitian Creole': { code: 'ht', skip: 'Sote', back: 'Retounen', next: 'Swivan', done: 'Ann kòmanse', help: 'Kijan sa mache', step: (n, m) => `Etap ${n} sou ${m}`,
      t: ['Byenvini nan SombraRoute', 'Kijan nou klase wout yo', 'Mache oswa pran transpò', 'Mande Gemma'],
      b: ['<p>Jwenn wout pou mache ki pi fre e pi konfòtab ant Downtown Miami ak Wynwood. Nou konpare kèk wout epi nou montre w sa ki pi bon pou lè a.</p>',
        '<ul><li><b>Lajounen:</b> plis lonbraj bilding ak pyebwa</li><li><b>Aswè:</b> lari ki byen klere ak kote ki louvri ta</li><li><b>Busiest:</b> lari ak magazen e moun k ap pase toutan</li><li>Mwens ensidan rapòte sou wout la</li><li>Mwens mache anba pon otowout</li></ul>',
        '<p>Sèvi ak bouton <b>Walk</b> ak <b>Transit</b> pou mache tout wout la oswa konbine Metromover gratis la ak ti mache kout.</p><p style="margin-top:8px">Peze <b>Start</b> pou swiv wout ou an dirèk sou kat la.</p>',
        '<p>Gemma rezime opsyon ou yo. Peze <b>Ask Gemma</b> pou poze kesyon tankou “Ki wout ki gen plis kote ki louvri pou kanpe?”</p><p style="margin-top:8px">Peze <b>EN</b>, <b>ES</b> (Español) oswa <b>KRE</b> (Kreyòl ayisyen) pou chanje lang lan.</p>'] },
  };
  let L = OB.English;
  const curLang = () => (document.querySelector('.lang.on') || {}).dataset?.lang || 'English';
  function render(name) {
    L = { ...OB.English, ...(OB[name] || {}) }; // missing strings fall back to English
    ob.lang = L.code;
    slides.forEach((s, k) => { s.querySelector('.ob-txt').innerHTML = `<h2 id="ob-t${k}">${L.t[k]}</h2>${L.b[k]}`; });
    [...dots.children].forEach((d, k) => d.setAttribute('aria-label', L.step(k + 1, slides.length)));
    document.getElementById('obskip').textContent = L.skip;
    document.querySelectorAll('#oblangs button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === name)));
    back.textContent = L.back;
    next.textContent = i === slides.length - 1 ? L.done : L.next;
    if (help) { help.setAttribute('aria-label', L.help); help.title = L.help; }
  }
  slides.forEach((_, k) => {
    const d = document.createElement('button');
    d.onclick = () => show(k);
    dots.appendChild(d);
  });
  function show(k) {
    i = Math.max(0, Math.min(slides.length - 1, k));
    slides.forEach((s, n) => { s.hidden = n !== i; });
    [...dots.children].forEach((d, n) => (n === i ? d.setAttribute('aria-current', 'step') : d.removeAttribute('aria-current')));
    ob.setAttribute('aria-labelledby', `ob-t${i}`);
    back.style.visibility = i ? 'visible' : 'hidden';
    next.textContent = i === slides.length - 1 ? L.done : L.next;
  }
  function open() { opener = document.activeElement; i = 0; render(curLang()); show(0); ob.hidden = false; next.focus(); }
  function close() {
    ob.hidden = true;
    try { localStorage.setItem('sombra_onboarded', '1'); } catch (e) { /* storage blocked: onboarding may show again */ }
    if (opener && opener.focus) opener.focus();
  }
  next.onclick = () => (i === slides.length - 1 ? close() : show(i + 1));
  back.onclick = () => show(i - 1);
  document.getElementById('obskip').onclick = close;
  ob.addEventListener('click', (e) => { if (e.target === ob) close(); });
  document.addEventListener('keydown', (e) => {
    if (ob.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopImmediatePropagation(); close(); }
    else if (e.key === 'ArrowRight') { e.preventDefault(); show(i + 1); }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); show(i - 1); }
    else if (e.key === 'Tab') {
      const f = [...ob.querySelectorAll('button')].filter((b) => b.offsetParent && b.style.visibility !== 'hidden');
      const a = f[0], z = f[f.length - 1];
      if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
      else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
    }
  }, true);
  let x0 = null;
  const card = document.getElementById('obcard');
  card.addEventListener('touchstart', (e) => { x0 = e.touches[0].clientX; }, { passive: true });
  card.addEventListener('touchend', (e) => {
    if (x0 === null) return;
    const dx = e.changedTouches[0].clientX - x0; x0 = null;
    if (Math.abs(dx) > 50) show(i + (dx < 0 ? 1 : -1));
  });
  help.className = 'ob-help'; help.id = 'obhelp'; help.textContent = '?';
  help.setAttribute('aria-haspopup', 'dialog'); help.onclick = open;
  document.body.appendChild(help);
  render(curLang());
  // Extra listener; the main script's onclick on .lang still runs.
  document.querySelectorAll('.lang').forEach((b) => b.addEventListener('click', () => { if (!ob.hidden) render(b.dataset.lang); }));
  // The overlay covers the sheet's buttons, so mirror them in the card (clicks the real one).
  document.querySelectorAll('#oblangs button').forEach((b) => b.onclick = () => { const r = document.querySelector(`.lang[data-lang="${b.dataset.lang}"]`); if (r) r.click(); });
  let seen = false;
  try { seen = localStorage.getItem('sombra_onboarded') === '1'; } catch (e) { /* storage blocked: treat as first visit */ }
  if (!seen) open();
})();
