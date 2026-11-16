'use strict';

/* =========================================================
   Liseuse : lecteur PDF / EPUB à défilement automatique
   Tout est stocké localement (IndexedDB), fonctionne hors ligne.
   ========================================================= */

const Core = window.LiseuseCore;
const $ = (s) => document.querySelector(s);
const scroller = $('#scroller');
const content = $('#content');
const readerView = $('#readerView');

const state = {
  book: null, playing: false, touching: false, pos: 0, last: 0,
  lastSave: 0, saveTimer: null, hideTimer: null, touchTimer: null,
  objectUrls: [], pdf: null, pages: [], observer: null, wakeLock: null,
  ratio: 0, resizing: false, resizeTimer: null,
  base: 0, lastStats: 0, seeking: false, seekTimer: null,
};

/* ---------- Réglages ---------- */
const settings = Object.assign({ speed: 30, theme: 'light', fontSize: 19, font: 'serif' }, loadSettings());
function loadSettings() { try { return JSON.parse(localStorage.getItem('liseuse-settings')) || {}; } catch { return {}; } }
function saveSettings() { try { localStorage.setItem('liseuse-settings', JSON.stringify(settings)); } catch {} }

/* ---------- IndexedDB ---------- */
let dbPromise;
function db() {
  if (!dbPromise) dbPromise = new Promise((res, rej) => {
    const r = indexedDB.open('liseuse', 1);
    r.onupgradeneeded = () => {
      r.result.createObjectStore('books', { keyPath: 'id' });
      r.result.createObjectStore('files');
    };
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
  return dbPromise;
}
async function tx(stores, mode, fn) {
  const d = await db();
  return new Promise((res, rej) => {
    const t = d.transaction(stores, mode);
    const req = fn(t);
    t.oncomplete = () => res(req && req.result);
    t.onerror = () => rej(t.error);
    t.onabort = () => rej(t.error || new Error('Stockage refusé (espace plein ?)'));
  });
}
const getAllBooks = () => tx('books', 'readonly', (t) => t.objectStore('books').getAll());
const putBook = (b) => tx('books', 'readwrite', (t) => t.objectStore('books').put(b));
const getFile = (id) => tx('files', 'readonly', (t) => t.objectStore('files').get(id));
const addBook = (meta, buf) => tx(['books', 'files'], 'readwrite', (t) => {
  t.objectStore('files').put(buf, meta.id);
  t.objectStore('books').put(meta);
});
const deleteBook = (id) => tx(['books', 'files'], 'readwrite', (t) => {
  t.objectStore('files').delete(id);
  t.objectStore('books').delete(id);
});

/* ---------- Utilitaires ---------- */
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));
const nextFrame = () => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function showLoading(t) { $('#loadingText').textContent = t || 'Chargement…'; $('#loading').classList.remove('hidden'); }
function setLoading(t) { $('#loadingText').textContent = t; }
function hideLoading() { $('#loading').classList.add('hidden'); }
function showView(name) {
  $('#library').classList.toggle('hidden', name !== 'library');
  readerView.classList.toggle('hidden', name !== 'reader');
}

/* ---------- Bibliothèque ---------- */
async function renderLibrary() {
  const books = (await getAllBooks()).sort((a, b) => (b.lastOpened || b.added) - (a.lastOpened || a.added));
  const list = $('#bookList');
  list.innerHTML = '';
  $('#empty').classList.toggle('hidden', books.length > 0);
  for (const b of books) {
    const p = Math.round((b.progress || 0) * 100);
    const li = document.createElement('li');
    li.className = 'book';
    li.innerHTML = `<div class="cover ${b.type}">${b.type.toUpperCase()}</div>
      <div class="info"><div class="title"></div><div class="meta"></div>
      <div class="progress"><span style="width:${p}%"></span></div></div>
      <button class="del" aria-label="Supprimer">✕</button>`;
    li.querySelector('.title').textContent = b.title;
    li.querySelector('.meta').textContent = `${p} % lu · ${Core.formatSize(b.size)}`;
    li.addEventListener('click', () => openBook(b.id));
    li.querySelector('.del').addEventListener('click', async (e) => {
      e.stopPropagation();
      if (confirm(`Retirer « ${b.title} » de la liseuse ?`)) { await deleteBook(b.id); renderLibrary(); }
    });
    list.appendChild(li);
  }
}

$('#addBtn').addEventListener('click', () => $('#fileInput').click());
$('#fileInput').addEventListener('change', async (e) => {
  const files = Array.from(e.target.files || []);
  e.target.value = '';
  if (files.length) await importFiles(files);
});

async function importFiles(files) {
  showLoading('Import…');
  for (const f of files) {
    try {
      const type = Core.detectType(f.name, f.type);
      if (!type) { alert(`« ${f.name} » n'est ni un PDF ni un EPUB.`); continue; }
      setLoading(`Import de ${f.name}…`);
      const buf = await f.arrayBuffer();
      let title = Core.titleFromFilename(f.name);
      if (type === 'epub') { try { title = (await epubTitle(buf)) || title; } catch {} }
      const hash = await fingerprint(buf);
      const twin = hash && (await getAllBooks()).find((b) => b.hash === hash);
      if (twin) { alert(`« ${twin.title} » est déjà dans la bibliothèque.`); continue; }
      await addBook({ id: uid(), title, type, size: f.size, added: Date.now(), lastOpened: 0, progress: 0, hash }, buf);
    } catch (err) {
      alert(`Impossible d'importer « ${f.name} » : ${err.message}`);
    }
  }
  hideLoading();
  renderLibrary();
}

// BIB-9 : empreinte SHA-256 du contenu (identique sur tous les appareils, prépare la synchro)
async function fingerprint(buf) {
  try {
    const d = await crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(d), (x) => x.toString(16).padStart(2, '0')).join('');
  } catch { return null; }
}

/* ---------- Ouverture / fermeture ---------- */
async function openBook(id) {
  const b = (await getAllBooks()).find((x) => x.id === id);
  if (!b) return;
  showLoading('Ouverture…');
  const buf = await getFile(id);
  if (!b.hash) b.hash = await fingerprint(buf); // livres importés avant BIB-9 (avant que pdf.js ne s'approprie buf)
  state.book = b;
  content.innerHTML = '';
  content.className = b.type;
  readerView.classList.toggle('is-pdf', b.type === 'pdf');
  $('#bookTitle').textContent = b.title;
  showView('reader');
  scroller.scrollTop = 0;
  try {
    if (b.type === 'pdf') await loadPdf(buf); else await loadEpub(buf);
  } catch (err) {
    hideLoading();
    alert(`Impossible d'ouvrir ce livre : ${err.message}`);
    closeBook();
    return;
  }
  applySettings();
  await nextFrame();
  restoreRatio(b.progress || 0);
  hideLoading();
  b.lastOpened = Date.now();
  putBook(b).catch(() => {});
  updateFsButton();
  updatePct(true);
  showBars();
}

// BIB-5 : on enregistre et on prépare la liste AVANT de l'afficher (pas d'ordre périmé à l'écran)
async function closeBook() {
  pause();
  const saving = saveProgress();
  if (state.observer) state.observer.disconnect();
  state.pages.forEach(releasePage);
  state.pages = [];
  if (state.pdf) { state.pdf.destroy(); state.pdf = null; }
  state.objectUrls.forEach((u) => URL.revokeObjectURL(u));
  state.objectUrls = [];
  content.innerHTML = '';
  state.book = null;
  closeSettings();
  await saving;
  await renderLibrary();
  showView('library');
}
$('#backBtn').addEventListener('click', closeBook);

/* ---------- Progression ---------- */
function currentRatio() {
  return Core.progressRatio(scroller.scrollTop, scroller.scrollHeight, scroller.clientHeight);
}
function restoreRatio(r) {
  const max = scroller.scrollHeight - scroller.clientHeight;
  clearSubpixel();
  scroller.scrollTop = Math.round(r * max);
  state.pos = state.base = scroller.scrollTop;
  state.ratio = r;
}
function saveProgress() {
  if (!state.book) return Promise.resolve();
  state.book.progress = currentRatio();
  window.LiseuseApp.lastSavedProgress = state.book.progress;
  state.book.lastOpened = Date.now();
  state.lastSave = Date.now();
  return putBook(state.book).catch(() => {});
}
// PROG-2, PROG-5, PROG-6, PROG-7, NAV-3. DEF-10 : au plus 4 fois par seconde pendant la lecture.
function setText(el, t) { if (el.textContent !== t) el.textContent = t; }
function updatePct(force) {
  const now = performance.now();
  if (!force && state.playing && now - state.lastStats < 250) return;
  state.lastStats = now;
  const r = currentRatio();
  setText($('#pct'), Math.round(r * 100) + ' %');
  setText($('#remaining'), Core.formatRemaining(
    Core.remainingSeconds(scroller.scrollTop, scroller.scrollHeight, scroller.clientHeight, settings.speed)));
  if (!state.seeking) seekInput.value = Math.round(r * 1000);
}

scroller.addEventListener('scroll', () => {
  if (!state.book || state.resizing) return;
  state.ratio = currentRatio();
  updatePct();
  clearTimeout(state.saveTimer);
  if (Date.now() - state.lastSave > 3000) saveProgress();
  else state.saveTimer = setTimeout(saveProgress, 800);
}, { passive: true });

document.addEventListener('visibilitychange', () => {
  if (document.hidden) { saveProgress(); if (state.playing) pause(); }
});
window.addEventListener('pagehide', saveProgress);

/* ---------- Défilement automatique ---------- */
const playBtn = $('#playBtn');
function atEnd() { return scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2; }

function play() {
  if (state.playing || !state.book) return;
  if (atEnd()) return;
  state.playing = true;
  state.pos = state.base = scroller.scrollTop;
  state.last = 0;
  playBtn.textContent = '❚❚';
  playBtn.setAttribute('aria-label', 'Pause');
  closeSettings();
  requestWake();
  requestAnimationFrame(tick);
  scheduleHide();
}
function pause() {
  if (!state.playing) return;
  state.playing = false;
  playBtn.textContent = '▶';
  playBtn.setAttribute('aria-label', 'Lecture');
  releaseWake();
  clearSubpixel();
  showBars();
  updatePct(true);
  saveProgress();
}
function tick(t) {
  if (!state.playing) return;
  if (state.last && !state.touching) {
    const dt = Math.min(t - state.last, 100) / 1000;
    // L'utilisateur a fait défiler à la main : on repart de sa position
    const top = scroller.scrollTop;
    if (Math.abs(top - state.base) > 1) state.pos = top;
    state.pos += settings.speed * dt;
    setVisual(state.pos);
    if (atEnd()) { pause(); return; }
  }
  state.last = t;
  requestAnimationFrame(tick);
}
playBtn.addEventListener('click', () => (state.playing ? pause() : play()));

// DEF-9 : iOS arrondit scrollTop au pixel, d'où des à-coups (1 px, 0, 1 px…).
// On défile donc de la partie entière, et on décale le texte de la partie
// décimale avec une transformation GPU : le mouvement devient continu.
function setVisual(pos) {
  const base = Math.floor(pos);
  if (base !== state.base) { scroller.scrollTop = base; state.base = base; }
  const frac = pos - base;
  content.style.transform = frac > 0.001 ? `translate3d(0, ${(-frac).toFixed(3)}px, 0)` : '';
}
function clearSubpixel() { content.style.transform = ''; }

// Glisser le doigt suspend le défilement, qui reprend tout seul après
scroller.addEventListener('touchstart', () => { state.touching = true; clearSubpixel(); clearTimeout(state.touchTimer); }, { passive: true });
const endTouch = () => { clearTimeout(state.touchTimer); state.touchTimer = setTimeout(() => { state.touching = false; }, 700); };
scroller.addEventListener('touchend', endTouch, { passive: true });
scroller.addEventListener('touchcancel', endTouch, { passive: true });

// Un toucher sur le texte = lecture / pause
scroller.addEventListener('click', (e) => {
  const a = e.target.closest('a');
  if (a) { e.preventDefault(); handleLink(a); return; }
  if (!$('#settings').classList.contains('hidden')) { closeSettings(); return; }
  state.playing ? pause() : play();
});

async function requestWake() {
  try { if ('wakeLock' in navigator) state.wakeLock = await navigator.wakeLock.request('screen'); } catch {}
}
function releaseWake() {
  try { if (state.wakeLock) state.wakeLock.release(); } catch {}
  state.wakeLock = null;
}

/* ---------- Barres ---------- */
function showBars() { readerView.classList.remove('bars-hidden'); clearTimeout(state.hideTimer); }
function hideBars() { readerView.classList.add('bars-hidden'); closeSettings(); }
function scheduleHide() {
  clearTimeout(state.hideTimer);
  state.hideTimer = setTimeout(() => { if (state.playing) hideBars(); }, 2000);
}

/* ---------- Vitesse ---------- */
const speedInput = $('#speed');
function setSpeed(v) {
  settings.speed = Core.clampSpeed(v);
  speedInput.value = settings.speed;
  $('#speedVal').textContent = settings.speed;
  saveSettings();
  if (state.book) updatePct(true);
}
const step = () => Core.speedStep(settings.speed);
speedInput.addEventListener('input', () => setSpeed(+speedInput.value));
$('#slower').addEventListener('click', () => { setSpeed(settings.speed - step()); if (state.playing) scheduleHide(); });
$('#faster').addEventListener('click', () => { setSpeed(settings.speed + step()); if (state.playing) scheduleHide(); });
['pointerdown', 'touchstart'].forEach((ev) => $('#bottomBar').addEventListener(ev, () => clearTimeout(state.hideTimer), { passive: true }));
['pointerup', 'touchend'].forEach((ev) => $('#bottomBar').addEventListener(ev, () => { if (state.playing) scheduleHide(); }, { passive: true }));

/* ---------- Navigation rapide (NAV-1..4) ---------- */
const seekInput = $('#seek');
const seekLabel = $('#seekLabel');
function sectionLabel(y) {
  const probe = y + scroller.clientHeight / 3;
  if (state.pdf) {
    const i = Core.locate(state.pages.map((st) => st.el.offsetTop), probe);
    return Core.pageLabel(Math.max(0, i), state.pages.length);
  }
  const secs = Array.from(content.querySelectorAll('.chapter'));
  const i = Core.locate(secs.map((s) => s.offsetTop), probe);
  if (i < 0) return '';
  const h = secs[i].querySelector('h1, h2, h3');
  const t = h && h.textContent.trim().replace(/\s+/g, ' ');
  return t ? (t.length > 60 ? t.slice(0, 57) + '…' : t) : `Chapitre ${i + 1}`;
}
function startSeek() {
  pause();
  state.seeking = true;
  clearTimeout(state.seekTimer);
  seekLabel.classList.remove('hidden');
}
seekInput.addEventListener('pointerdown', startSeek);
seekInput.addEventListener('touchstart', startSeek, { passive: true });
seekInput.addEventListener('input', () => {
  if (!state.seeking) startSeek();
  const r = seekInput.value / 1000;
  restoreRatio(r);
  seekLabel.textContent = sectionLabel(scroller.scrollTop);
  updatePct(true);
});
seekInput.addEventListener('change', () => {
  state.seeking = false;
  saveProgress();
  clearTimeout(state.seekTimer);
  state.seekTimer = setTimeout(() => seekLabel.classList.add('hidden'), 1200);
});

/* ---------- Plein écran (AFF-8) ---------- */
const fsBtn = $('#fsBtn');
function isInstalled() {
  return navigator.standalone === true ||
    ['standalone', 'fullscreen'].some((m) => window.matchMedia(`(display-mode: ${m})`).matches);
}
function fsSupported() { return !!(document.fullscreenEnabled || document.webkitFullscreenEnabled); }
function updateFsButton() { fsBtn.classList.toggle('hidden', !fsSupported() || isInstalled()); }
fsBtn.addEventListener('click', () => {
  const d = document, el = d.documentElement;
  if (d.fullscreenElement || d.webkitFullscreenElement) (d.exitFullscreen || d.webkitExitFullscreen).call(d);
  else (el.requestFullscreen || el.webkitRequestFullscreen).call(el);
});

/* ---------- Affichage ---------- */
function applySettings() {
  document.documentElement.dataset.theme = settings.theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  const body = content.querySelector('.epub-body');
  if (body) {
    body.style.setProperty('--fs', settings.fontSize);
    body.classList.toggle('sans', settings.font === 'sans');
  }
  $('#fontVal').textContent = settings.fontSize;
  document.querySelectorAll('#themeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.theme === settings.theme));
  document.querySelectorAll('#fontSeg button').forEach((b) => b.classList.toggle('on', b.dataset.font === settings.font));
}
function changeLayout(fn) {
  const r = currentRatio();
  fn();
  saveSettings();
  applySettings();
  requestAnimationFrame(() => restoreRatio(r));
}
document.querySelectorAll('#themeSeg button').forEach((b) => b.addEventListener('click', () => { settings.theme = b.dataset.theme; saveSettings(); applySettings(); }));
document.querySelectorAll('#fontSeg button').forEach((b) => b.addEventListener('click', () => changeLayout(() => { settings.font = b.dataset.font; })));
$('#fontDown').addEventListener('click', () => changeLayout(() => { settings.fontSize = Core.clampFontSize(settings.fontSize - 1); }));
$('#fontUp').addEventListener('click', () => changeLayout(() => { settings.fontSize = Core.clampFontSize(settings.fontSize + 1); }));

function closeSettings() { $('#settings').classList.add('hidden'); }
$('#settingsBtn').addEventListener('click', () => {
  pause();
  $('#settings').classList.toggle('hidden');
});

/* ---------- PDF ---------- */
async function loadPdf(buf) {
  pdfjsLib.GlobalWorkerOptions.workerSrc = 'vendor/pdf.worker.min.js';
  const pdf = await pdfjsLib.getDocument({ data: new Uint8Array(buf), isEvalSupported: false }).promise;
  state.pdf = pdf;
  state.pages = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    if (i % 10 === 0) setLoading(`Préparation des pages ${i}/${pdf.numPages}…`);
    const page = await pdf.getPage(i);
    const vp = page.getViewport({ scale: 1 });
    const el = document.createElement('div');
    el.className = 'page';
    el.style.aspectRatio = `${vp.width} / ${vp.height}`;
    el.dataset.i = i - 1;
    content.appendChild(el);
    state.pages.push({ el, page, w: vp.width, visible: false, canvas: null, task: null, rendering: false });
  }
  state.observer = new IntersectionObserver((entries) => {
    for (const en of entries) {
      const st = state.pages[+en.target.dataset.i];
      if (!st) continue;
      st.visible = en.isIntersecting;
      if (en.isIntersecting) renderPage(st); else releasePage(st);
    }
  }, { root: scroller, rootMargin: '100% 0px 200% 0px' });
  state.pages.forEach((st) => state.observer.observe(st.el));
}

async function renderPage(st) {
  if (st.canvas || st.rendering || !state.pdf) return;
  st.rendering = true;
  let cancelled = false;
  try {
    const dpr = Math.min(window.devicePixelRatio || 1, 2.5);
    let scale = (st.el.clientWidth / st.w) * dpr;
    const probe = st.page.getViewport({ scale });
    const maxPx = 7e6; // limite mémoire des canvas sur iOS
    if (probe.width * probe.height > maxPx) scale *= Math.sqrt(maxPx / (probe.width * probe.height));
    const vp = st.page.getViewport({ scale });
    const c = document.createElement('canvas');
    c.width = Math.floor(vp.width);
    c.height = Math.floor(vp.height);
    st.task = st.page.render({ canvasContext: c.getContext('2d'), viewport: vp });
    await st.task.promise;
    if (st.visible && state.pdf) { st.el.appendChild(c); st.canvas = c; }
    else { c.width = c.height = 0; }
  } catch (e) {
    cancelled = e && e.name === 'RenderingCancelledException';
  } finally {
    st.task = null;
    st.rendering = false;
  }
  if (cancelled && st.visible && !st.canvas) renderPage(st);
}

function releasePage(st) {
  if (st.task) { try { st.task.cancel(); } catch {} }
  if (st.canvas) { st.canvas.width = st.canvas.height = 0; st.canvas.remove(); st.canvas = null; }
}

// AFF-6 / PDF-4 : à la rotation, la mise en page change avant l'événement « resize ».
// On restaure donc la dernière position connue (state.ratio), pas celle mesurée maintenant.
function onResize() {
  if (!state.book) return;
  const r = state.ratio;
  state.resizing = true;
  restoreRatio(r);
  clearTimeout(state.resizeTimer);
  state.resizeTimer = setTimeout(() => {
    if (state.pdf) state.pages.forEach(releasePage);
    restoreRatio(r);
    state.resizing = false;
    updatePct();
    if (state.pdf) state.pages.filter((st) => st.visible).forEach(renderPage);
  }, 250);
}
window.addEventListener('resize', onResize);

/* ---------- EPUB ---------- */
const parseXml = (t) => new DOMParser().parseFromString(t, 'application/xml');
const byTag = (d, n) => Array.from(d.getElementsByTagNameNS('*', n));
const { dirOf, resolvePath, mimeOf } = Core;
function zipFile(zip, path) {
  const f = zip.file(path);
  if (f) return f;
  const k = Object.keys(zip.files).find((x) => x.toLowerCase() === path.toLowerCase());
  return k ? zip.file(k) : null;
}
async function readOpf(zip) {
  const cf = zipFile(zip, 'META-INF/container.xml');
  if (!cf) throw new Error('EPUB invalide (container.xml manquant)');
  const rf = byTag(parseXml(await cf.async('text')), 'rootfile')[0];
  const opfPath = rf && rf.getAttribute('full-path');
  const of = opfPath && zipFile(zip, opfPath);
  if (!of) throw new Error('EPUB invalide (fichier OPF introuvable)');
  return { opf: parseXml(await of.async('text')), base: dirOf(opfPath) };
}
async function epubTitle(buf) {
  const { opf } = await readOpf(await JSZip.loadAsync(buf));
  const t = byTag(opf, 'title')[0];
  return t && t.textContent.trim();
}

async function loadEpub(buf) {
  const zip = await JSZip.loadAsync(buf);
  const { opf, base } = await readOpf(zip);
  const manifest = {};
  for (const it of byTag(opf, 'item')) {
    manifest[it.getAttribute('id')] = { href: resolvePath(base, it.getAttribute('href') || '') };
  }
  const spine = byTag(opf, 'itemref').map((r) => manifest[r.getAttribute('idref')]).filter(Boolean);
  if (!spine.length) throw new Error('aucun chapitre trouvé');
  const chapterIndex = new Map(spine.map((it, i) => [it.href, i]));
  const urlCache = new Map();
  const getUrl = async (path) => {
    if (urlCache.has(path)) return urlCache.get(path);
    const f = zipFile(zip, path);
    let u = null;
    if (f) {
      u = URL.createObjectURL(new Blob([await f.async('uint8array')], { type: mimeOf(path) }));
      state.objectUrls.push(u);
    }
    urlCache.set(path, u);
    return u;
  };

  const wrap = document.createElement('div');
  wrap.className = 'epub-body';
  const lang = byTag(opf, 'language')[0];
  wrap.lang = (lang && lang.textContent.trim()) || 'fr';

  for (let i = 0; i < spine.length; i++) {
    setLoading(`Chapitre ${i + 1}/${spine.length}…`);
    const f = zipFile(zip, spine[i].href);
    if (!f) continue;
    const text = await f.async('text');
    let doc = new DOMParser().parseFromString(text, 'application/xhtml+xml');
    if (doc.getElementsByTagName('parsererror').length || !doc.body) doc = new DOMParser().parseFromString(text, 'text/html');
    const body = doc.body || byTag(doc, 'body')[0];
    if (!body) continue;
    await sanitize(body, { i, cdir: dirOf(spine[i].href), chapterIndex, getUrl });
    const sec = document.createElement('section');
    sec.className = 'chapter';
    sec.id = `c${i}`;
    for (const n of Array.from(body.childNodes)) sec.appendChild(document.importNode(n, true));
    wrap.appendChild(sec);
  }
  content.appendChild(wrap);
  // Attendre les images pour que la position de reprise soit juste
  const imgs = Array.from(wrap.querySelectorAll('img'));
  await Promise.race([
    Promise.all(imgs.map((im) => (im.complete ? null : new Promise((r) => { im.onload = im.onerror = r; })))),
    sleep(4000),
  ]);
}

const BLOCKED = new Set(['script', 'style', 'link', 'iframe', 'object', 'embed', 'meta', 'base', 'form', 'input',
  'button', 'textarea', 'select', 'audio', 'video', 'frame', 'frameset', 'foreignobject']);
const XLINK = 'http://www.w3.org/1999/xlink';

async function sanitize(root, ctx) {
  for (const el of Array.from(root.getElementsByTagName('*'))) {
    const tag = el.localName.toLowerCase();
    if (BLOCKED.has(tag)) { el.remove(); continue; }
    for (const a of Array.from(el.attributes)) {
      const n = a.name.toLowerCase();
      if (n.startsWith('on') || n === 'style' || n === 'srcset') el.removeAttribute(a.name);
    }
    if (el.id) el.id = `c${ctx.i}-${el.id}`;

    if (tag === 'img') {
      const src = el.getAttribute('src') || '';
      if (/^data:image\//i.test(src)) continue;
      const u = src && !/^[a-z]+:/i.test(src) ? await ctx.getUrl(resolvePath(ctx.cdir, src)) : null;
      if (u) el.setAttribute('src', u); else el.remove();
    } else if (tag === 'image') {
      const href = el.getAttribute('href') || el.getAttributeNS(XLINK, 'href') || '';
      const u = href && !/^[a-z]+:/i.test(href) ? await ctx.getUrl(resolvePath(ctx.cdir, href)) : null;
      el.removeAttribute('href');
      el.removeAttributeNS(XLINK, 'href');
      if (u) el.setAttributeNS(XLINK, 'xlink:href', u); else el.remove();
    } else if (tag === 'a') {
      const href = el.getAttribute('href') || el.getAttributeNS(XLINK, 'href') || '';
      el.removeAttribute('href');
      el.removeAttributeNS(XLINK, 'href');
      const link = Core.linkTarget(href, { chapter: ctx.i, dir: ctx.cdir, index: ctx.chapterIndex });
      if (link && link.type === 'external') el.setAttribute('data-ext', link.url);
      else if (link) el.setAttribute('data-target', link.id);
      if (el.hasAttribute('data-ext') || el.hasAttribute('data-target')) el.setAttribute('href', '#');
    }
  }
}

function handleLink(a) {
  const target = a.getAttribute('data-target');
  const ext = a.getAttribute('data-ext');
  if (target) {
    const el = document.getElementById(target);
    if (el) {
      pause();
      scroller.scrollTop += el.getBoundingClientRect().top - scroller.getBoundingClientRect().top - 70;
      state.pos = scroller.scrollTop;
    }
  } else if (ext && confirm(`Ouvrir ce lien dans le navigateur ?\n${ext}`)) {
    window.open(ext, '_blank', 'noopener');
  }
}

/* ---------- Démarrage ---------- */
// Points d'observation pour les tests automatiques (lecture seule)
window.LiseuseApp = { ready: false, lastSavedProgress: null };
setSpeed(settings.speed);
applySettings();
renderLibrary().then(() => { window.LiseuseApp.ready = true; });
if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
