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
const settings = Object.assign({ speed: 30, theme: 'light', fontSize: 19, font: 'serif',
  autoTheme: false, dayTheme: 'light', nightTheme: 'night', ttsRate: 1, ttsVoice: null, pdfZoom: 1 }, loadSettings());
const darkQuery = window.matchMedia('(prefers-color-scheme: dark)');
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
  state.bookLang = 'fr';
  fillVoices();
  resetSearch();
  content.innerHTML = '';
  content.className = b.type;
  clearSubpixel();
  // AFF-12 : zoom mémorisé pour les PDF
  const z = b.type === 'pdf' ? settings.pdfZoom || 1 : 1;
  content.style.setProperty('--z', z);
  scroller.classList.toggle('zoomed', z > 1);
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
  ttsStop();
  closeSearch();
  resetSearch();
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
  if (document.hidden) { saveProgress(); if (state.playing) pause(); if (tts.state === 'playing') ttsPause(); }
});
window.addEventListener('pagehide', saveProgress);

/* ---------- Défilement automatique ---------- */
const playBtn = $('#playBtn');
function atEnd() { return scroller.scrollTop + scroller.clientHeight >= scroller.scrollHeight - 2; }

function play() {
  if (state.playing || !state.book) return;
  if (tts.state) ttsStop();
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
  setShift(frac > 0.001 ? -frac : 0);
}
// DEF-12 : la couche graphique du texte n'est jamais détruite (sinon l'iPhone redessine tout)
const REST = 'translate3d(0, 0, 0)';
function setShift(y) {
  const t = y ? `translate3d(0, ${y.toFixed(3)}px, 0)` : REST;
  if (content.style.transform !== t) content.style.transform = t;
}
function clearSubpixel() { setShift(0); }

// Glisser le doigt suspend le défilement, qui reprend tout seul après
scroller.addEventListener('touchstart', () => { state.touching = true; tts.holdUntil = performance.now() + 3000; tts.anim++; clearSubpixel(); clearTimeout(state.touchTimer); }, { passive: true });
const endTouch = () => { tts.holdUntil = performance.now() + 3000; clearTimeout(state.touchTimer); state.touchTimer = setTimeout(() => { state.touching = false; }, 700); };
scroller.addEventListener('touchend', endTouch, { passive: true });
scroller.addEventListener('touchcancel', endTouch, { passive: true });

// AFF-12 : l'app ne zoome jamais en entier ; le pincement règle le texte (EPUB) ou les pages (PDF)
// AFF-13 : si iOS a malgré tout laissé la page zoomée, on le laisse dézoomer
const pageZoomed = () => !!(window.visualViewport && Math.abs(window.visualViewport.scale - 1) > 0.01);
['gesturestart', 'gesturechange', 'gestureend'].forEach((t) => document.addEventListener(t, (e) => { if (!pageZoomed()) e.preventDefault(); }));
// DEF-11 : le zoom est bloqué en CSS (touch-action), jamais par un écouteur bloquant ;
// la classe page-zoomed rend la main à iOS si la page est restée zoomée
const syncZoomed = () => document.documentElement.classList.toggle('page-zoomed', pageZoomed());
if (window.visualViewport) window.visualViewport.addEventListener('resize', syncZoomed);
const pinch = { on: false, d0: 0, start: 0, value: 0, ratio: 0, cx: 0 };
const fingerGap = (t) => Math.hypot(t[0].clientX - t[1].clientX, t[0].clientY - t[1].clientY);
function applyPdfZoom(z, cx) {
  const old = parseFloat(content.style.getPropertyValue('--z')) || 1;
  const left = scroller.scrollLeft;
  content.style.setProperty('--z', z);
  scroller.classList.toggle('zoomed', z > 1);
  restoreRatio(pinch.ratio);
  if (cx != null) scroller.scrollLeft = (left + cx) * z / old - cx;
}
scroller.addEventListener('touchstart', (e) => {
  if (!state.book || !e.touches || e.touches.length !== 2) return;
  clearTimeout(press.timer); press.timer = null;
  state.suppressClick = true;
  pinch.on = true;
  pinch.d0 = fingerGap(e.touches);
  pinch.start = pinch.value = state.pdf ? settings.pdfZoom : settings.fontSize;
  pinch.ratio = currentRatio();
  const rc = scroller.getBoundingClientRect();
  pinch.cx = (e.touches[0].clientX + e.touches[1].clientX) / 2 - rc.left;
}, { passive: true });
scroller.addEventListener('touchmove', (e) => {
  if (!pinch.on || !e.touches || e.touches.length < 2 || pageZoomed()) return;
  const v = state.pdf ? Core.pinchValue(pinch.start, pinch.d0, fingerGap(e.touches), 1, 3, 0.05)
    : Core.pinchValue(pinch.start, pinch.d0, fingerGap(e.touches), Core.FONT_MIN, Core.FONT_MAX, 1);
  if (v === pinch.value) return;
  pinch.value = v;
  if (state.pdf) { settings.pdfZoom = v; applyPdfZoom(v, pinch.cx); }
  else { settings.fontSize = v; applySettings(); restoreRatio(pinch.ratio); }
}, { passive: true });
function endPinch(e) {
  if (!pinch.on || (e.touches && e.touches.length >= 2)) return;
  pinch.on = false;
  // le « click » éventuel du geste est ignoré, puis on oublie le drapeau
  setTimeout(() => { state.suppressClick = false; }, 400);
  if (pinch.value === pinch.start) return;
  saveSettings();
  restoreRatio(pinch.ratio);
  if (state.pdf) {
    state.pages.forEach(releasePage);
    restoreRatio(pinch.ratio);
    state.pages.filter((st) => st.visible).forEach(renderPage);
  }
}
scroller.addEventListener('touchend', endPinch, { passive: true });
scroller.addEventListener('touchcancel', endPinch, { passive: true });

// Un toucher sur le texte = lecture / pause
scroller.addEventListener('click', (e) => {
  const a = e.target.closest('a');
  if (a) { e.preventDefault(); handleLink(a); return; }
  if (state.suppressClick) { state.suppressClick = false; return; }
  if (!$('#settings').classList.contains('hidden')) { closeSettings(); return; }
  if (tts.state) { tts.state === 'playing' ? ttsPause() : ttsResume(); return; }
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

/* ---------- Recherche (SRCH-1..7) ---------- */
const searchPanel = $('#searchPanel'), searchInput = $('#searchInput');
const searchStatus = $('#searchStatus'), searchResults = $('#searchResults');
const SEARCH_MAX = 200;
const search = { index: null, building: null, timer: null, token: 0 };

function resetSearch() {
  search.index = null; search.building = null; search.token++;
  searchInput.value = '';
  setSearchStatus('', '');
  searchResults.innerHTML = '';
}
function setSearchStatus(text, query) {
  searchStatus.textContent = text;
  searchStatus.dataset.query = query;
}
function openSearch() {
  pause();
  closeSettings();
  searchPanel.classList.remove('hidden');
  searchInput.focus();
}
function closeSearch() { searchPanel.classList.add('hidden'); searchInput.blur(); }
$('#searchBtn').addEventListener('click', openSearch);
$('#searchClose').addEventListener('click', closeSearch);
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !searchPanel.classList.contains('hidden')) closeSearch();
});
searchInput.addEventListener('input', () => {
  clearTimeout(search.timer);
  search.timer = setTimeout(runSearch, 200);
});
searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') { clearTimeout(search.timer); runSearch(); searchInput.blur(); } });

function chapterTitle(sec, i) {
  const h = sec.querySelector('h1, h2, h3');
  const t = h && h.textContent.trim().replace(/\s+/g, ' ');
  return t ? (t.length > 60 ? t.slice(0, 57) + '…' : t) : `Chapitre ${i + 1}`;
}

// Index du texte, construit une seule fois par livre ouvert
const BLOCK = 'p,div,h1,h2,h3,h4,h5,h6,li,blockquote,section,td,th,pre,dt,dd,figcaption';
async function buildIndex(progress) {
  const units = [];
  if (state.pdf) {
    const n = state.pages.length;
    for (let i = 0; i < n; i++) {
      if (i % 5 === 0 && progress) progress(i + 1, n);
      const st = state.pages[i];
      const tc = await st.page.getTextContent();
      let text = '';
      const parts = [];
      for (const it of tc.items) {
        if (!('str' in it) || !it.str) continue;
        if (text) text += ' ';
        parts.push({ item: it, start: text.length });
        text += it.str;
      }
      units.push({ kind: 'pdf', st, el: st.el, label: Core.pageLabel(i, n), text, parts, breaks: [] });
    }
  } else {
    content.querySelectorAll('.chapter').forEach((sec, i) => {
      let text = '', lastBlock = null;
      const parts = [], breaks = [];
      const walker = document.createTreeWalker(sec, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode()) {
        if (!node.data) continue;
        const block = node.parentElement && node.parentElement.closest(BLOCK);
        if (text && block !== lastBlock) { text += ' '; breaks.push(text.length); }
        lastBlock = block;
        parts.push({ node, start: text.length });
        text += node.data;
      }
      units.push({ kind: 'epub', el: sec, label: chapterTitle(sec, i), text, parts, breaks });
    });
  }
  for (const u of units) { u.folded = Core.foldText(u.text); u.starts = u.parts.map((p) => p.start); }
  return units;
}

// Index partagé par la recherche et la lecture à voix haute
async function textIndex(progress) {
  if (!search.index) {
    if (!search.building) search.building = buildIndex(progress);
    const building = search.building;
    const idx = await building;
    if (building !== search.building) return null; // un autre livre a été ouvert entre-temps
    search.index = idx;
  }
  return search.index;
}

async function runSearch() {
  const query = searchInput.value;
  const token = ++search.token;
  searchResults.innerHTML = '';
  if (Core.foldText(query).text.trim().length < 2) {
    setSearchStatus(query.trim() ? 'Tapez au moins 2 caractères' : '', query);
    return;
  }
  const idx = await textIndex((i, n) => setSearchStatus(`Préparation de la recherche… page ${i}/${n}`, ''));
  if (!idx || token !== search.token) return;
  if (state.pdf && search.index.every((u) => !u.text.trim())) {
    setSearchStatus('Ce PDF ne contient pas de texte cherchable', query);
    return;
  }
  const hits = [];
  for (const u of search.index) {
    for (const m of Core.searchFolded(u.folded, query, SEARCH_MAX + 1 - hits.length)) hits.push({ u, m });
    if (hits.length > SEARCH_MAX) break;
  }
  const frag = document.createDocumentFragment();
  for (const h of hits.slice(0, SEARCH_MAX)) {
    const s = Core.snippet(h.u.text, h.m.start, h.m.end, 40);
    const li = document.createElement('li');
    const loc = document.createElement('span'); loc.className = 'loc'; loc.textContent = h.u.label;
    const snip = document.createElement('span'); snip.className = 'snip';
    const mark = document.createElement('mark'); mark.textContent = s.match;
    snip.append(s.before, mark, s.after);
    li.append(loc, snip);
    li.addEventListener('click', () => goToHit(h));
    frag.appendChild(li);
  }
  searchResults.appendChild(frag);
  searchResults.scrollTop = 0;
  setSearchStatus(Core.resultCount(hits.length, SEARCH_MAX), query);
}

function partAt(u, idx) {
  const k = Math.max(0, Core.locate(u.starts, idx));
  return { part: u.parts[k], off: idx - u.parts[k].start };
}

function jumpTo(y) {
  clearSubpixel();
  const max = scroller.scrollHeight - scroller.clientHeight;
  scroller.scrollTop = Math.max(0, Math.min(max, Math.round(y - scroller.clientHeight / 3)));
  state.pos = state.base = scroller.scrollTop;
  state.ratio = currentRatio();
  updatePct(true);
  saveProgress();
}

function addHit(parent, left, top, width, height) {
  const d = document.createElement('div');
  d.className = 'search-hit';
  Object.assign(d.style, { left: left + 'px', top: top + 'px', width: Math.max(4, width) + 'px', height: height + 'px' });
  parent.appendChild(d);
  setTimeout(() => d.remove(), 3600);
}

// Rectangle (dans la page) d'un morceau de texte PDF, du caractère `from` au caractère `to`
function pdfItemRect(st, item, from, to) {
  const scale = st.el.clientWidth / st.w;
  const vp = st.page.getViewport({ scale });
  const tx = pdfjsLib.Util.transform(vp.transform, item.transform);
  const h = Math.hypot(tx[2], tx[3]);
  const w = item.width * scale, len = Math.max(1, item.str.length);
  const a = Math.max(0, from), b = Math.min(len, to);
  return { left: tx[4] + w * (a / len), top: tx[5] - h, width: w * ((b - a) / len), height: h * 1.25 };
}

function goToHit({ u, m }) {
  closeSearch();
  pause();
  content.querySelectorAll('.search-hit').forEach((d) => d.remove());
  if (u.kind === 'epub') {
    const a = partAt(u, m.start), b = partAt(u, m.end - 1);
    const range = document.createRange();
    range.setStart(a.part.node, Math.min(a.off, a.part.node.length));
    range.setEnd(b.part.node, Math.min(b.off + 1, b.part.node.length));
    const first = range.getClientRects()[0] || range.getBoundingClientRect();
    jumpTo(scroller.scrollTop + first.top - scroller.getBoundingClientRect().top);
    const base = content.getBoundingClientRect();
    for (const r of Array.from(range.getClientRects()).slice(0, 6)) {
      addHit(content, r.left - base.left - 1, r.top - base.top - 1, r.width + 2, r.height + 2);
    }
  } else {
    const { part, off } = partAt(u, m.start);
    const st = u.st, it = part.item;
    const scale = st.el.clientWidth / st.w;
    const vp = st.page.getViewport({ scale });
    const tx = pdfjsLib.Util.transform(vp.transform, it.transform);
    const h = Math.hypot(tx[2], tx[3]);
    const w = it.width * scale, len = Math.max(1, it.str.length);
    const left = tx[4] + w * (off / len);
    const width = w * (Math.min(len - off, m.end - m.start) / len);
    const top = tx[5] - h;
    jumpTo(st.el.offsetTop + top);
    addHit(st.el, left - 1, top - 2, width + 2, h * 1.25 + 2);
  }
}

/* ---------- Lecture à voix haute (TTS-1..10) ---------- */
const synth = window.speechSynthesis;
const ttsSupported = !!(synth && typeof window.SpeechSynthesisUtterance === 'function');
const tts = {
  state: '', units: null, u: 0, s: 0, token: 0, holdUntil: 0,
  sleepOpt: null, deadline: null, sleepTimer: null, anim: 0,
};
$('#ttsBtn').classList.toggle('hidden', !ttsSupported);
// iOS charge la liste des voix après coup
if (ttsSupported && synth.addEventListener) synth.addEventListener('voiceschanged', () => fillVoices());

const sentencesOf = (u) => u.sentences || (u.sentences = Core.splitSentences(u.text, 250, u.breaks));
function setTtsState(st) {
  tts.state = st;
  readerView.dataset.tts = st;
  readerView.classList.toggle('tts-on', !!st);
  const b = $('#ttsPlay');
  b.textContent = st === 'playing' ? '❚❚' : '▶';
  b.setAttribute('aria-label', st === 'playing' ? 'Pause voix' : 'Reprendre la voix');
}

// Boîtes d'une phrase : { parent, left, top, width, height } (coordonnées dans parent) + haut/bas à l'écran
function sentenceBoxes(u, a, b) {
  const boxes = [];
  if (u.kind === 'epub') {
    const pa = partAt(u, a), pb = partAt(u, b - 1);
    const range = document.createRange();
    range.setStart(pa.part.node, Math.min(Math.max(0, pa.off), pa.part.node.length));
    range.setEnd(pb.part.node, Math.min(Math.max(0, pb.off + 1), pb.part.node.length));
    const base = content.getBoundingClientRect();
    for (const r of Array.from(range.getClientRects())) {
      if (r.width < 1 || r.height < 1) continue;
      boxes.push({ parent: content, left: r.left - base.left, top: r.top - base.top, width: r.width, height: r.height,
        vTop: r.top, vBottom: r.bottom });
    }
  } else {
    const pr = u.st.el.getBoundingClientRect();
    for (const p of u.parts) {
      const end = p.start + p.item.str.length;
      if (end <= a || p.start >= b) continue;
      const r = pdfItemRect(u.st, p.item, a - p.start, b - p.start);
      boxes.push({ parent: u.st.el, ...r, vTop: pr.top + r.top, vBottom: pr.top + r.top + r.height });
    }
  }
  return boxes;
}

function clearTtsHit() { content.querySelectorAll('.tts-hit').forEach((d) => d.remove()); }

function animateScrollTo(target) {
  const max = scroller.scrollHeight - scroller.clientHeight;
  target = Math.max(0, Math.min(max, Math.round(target)));
  const from = scroller.scrollTop, t0 = performance.now(), dur = 300, id = ++tts.anim;
  let written = from;
  clearSubpixel();
  const step = (now) => {
    // l'utilisateur a touché ou fait défiler : on lui laisse la main
    if (id !== tts.anim || Math.abs(scroller.scrollTop - written) > 2) return;
    const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    scroller.scrollTop = written = Math.round(from + (target - from) * e);
    state.pos = state.base = scroller.scrollTop;
    if (k < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// TTS-4 : surligner la phrase et la garder entre 15 % et 60 % de l'écran
function showSentence() {
  const u = tts.units[tts.u], [a, b] = sentencesOf(u)[tts.s];
  clearTtsHit();
  const boxes = sentenceBoxes(u, a, b);
  for (const x of boxes) {
    const d = document.createElement('div');
    d.className = 'tts-hit';
    Object.assign(d.style, { left: x.left - 1 + 'px', top: x.top - 1 + 'px', width: x.width + 2 + 'px', height: x.height + 2 + 'px' });
    x.parent.appendChild(d);
  }
  if (!boxes.length || performance.now() < tts.holdUntil) return;
  const sTop = scroller.getBoundingClientRect().top, H = scroller.clientHeight;
  const top = boxes[0].vTop - sTop, bottom = Math.max(...boxes.map((x) => x.vBottom)) - sTop;
  if (top < 0.15 * H || bottom > 0.6 * H) animateScrollTo(scroller.scrollTop + top - H / 3);
}

function currentVoice() {
  const voices = synth.getVoices() || [];
  const id = Core.pickVoice(voices, state.bookLang || 'fr', settings.ttsVoice);
  return voices.find((v) => (v.voiceURI || v.name) === id) || null;
}

// TTS-11 : choix de la voix dans le panneau Aa
function fillVoices() {
  const sel = $('#voiceSelect');
  if (!ttsSupported) return;
  const choices = Core.voiceChoices(synth.getVoices() || [], state.bookLang || 'fr');
  sel.replaceChildren();
  const auto = document.createElement('option');
  auto.value = ''; auto.textContent = 'Automatique (la meilleure)';
  sel.appendChild(auto);
  for (const c of choices) {
    const o = document.createElement('option');
    o.value = c.id; o.textContent = c.label;
    sel.appendChild(o);
  }
  sel.value = choices.some((c) => c.id === settings.ttsVoice) ? settings.ttsVoice : '';
  document.querySelectorAll('.voice-row').forEach((el) => el.classList.toggle('hidden', !choices.length));
}

function speakCurrent() {
  const token = ++tts.token;
  try { synth.cancel(); } catch {}
  const u = tts.units[tts.u], [a, b] = sentencesOf(u)[tts.s];
  showSentence();
  const ut = new SpeechSynthesisUtterance(u.text.slice(a, b).replace(/\s+/g, ' '));
  const v = currentVoice();
  if (v) ut.voice = v;
  ut.lang = v ? v.lang : (state.bookLang || 'fr-FR');
  ut.rate = settings.ttsRate;
  ut.onend = () => { if (token === tts.token) onSentenceEnd(); };
  ut.onerror = (e) => {
    if (token !== tts.token || (e && /interrupted|canceled/.test(e.error))) return;
    onSentenceEnd();
  };
  synth.speak(ut);
}

// Position suivante / précédente (en sautant les unités sans texte)
function neighbour(dir) {
  let { u, s } = tts;
  s += dir;
  while (u >= 0 && u < tts.units.length) {
    const n = sentencesOf(tts.units[u]).length;
    if (s >= 0 && s < n) return { u, s };
    u += dir;
    if (u < 0 || u >= tts.units.length) break;
    s = dir > 0 ? 0 : sentencesOf(tts.units[u]).length - 1;
  }
  return null;
}

function onSentenceEnd() {
  if (tts.state !== 'playing') return;
  const nxt = neighbour(1);
  if (!nxt || (tts.deadline && Date.now() >= tts.deadline) || (tts.sleepOpt === 'chapter' && nxt.u !== tts.u)) {
    ttsStop();
    return;
  }
  tts.u = nxt.u; tts.s = nxt.s;
  speakCurrent();
}

async function ttsStartAt(locate) {
  if (!ttsSupported || !state.book) return;
  const units = await textIndex((i, n) => { showLoading(`Préparation de la lecture… page ${i}/${n}`); });
  hideLoading();
  if (!units || !state.book) return;
  if (!units.some((u) => sentencesOf(u).length)) { alert('Ce PDF ne contient pas de texte à lire'); return; }
  const pos = locate(units);
  if (!pos) return;
  pause();
  tts.units = units; tts.u = pos.u; tts.s = pos.s;
  setTtsState('playing');
  showBars();
  $('#ttsRate').textContent = Core.formatRate(settings.ttsRate);
  updateSleepLabel();
  requestWake();
  speakCurrent();
}

// TTS-1 : première phrase qui commence sous la barre du haut
function locateTop(units) {
  const sTop = scroller.getBoundingClientRect().top;
  const bar = $('#topBar').getBoundingClientRect();
  const y = Math.max(bar.bottom, sTop);
  let k = Math.max(0, Core.locate(units.map((u) => u.el.offsetTop), scroller.scrollTop + (y - sTop)));
  for (; k < units.length; k++) {
    const sents = sentencesOf(units[k]);
    let lo = 0, hi = sents.length - 1, found = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      const bx = sentenceBoxes(units[k], sents[mid][0], sents[mid][1])[0];
      if (bx && bx.vTop >= y - 2) { found = mid; hi = mid - 1; } else lo = mid + 1;
    }
    if (found >= 0) return { u: k, s: found };
  }
  return null;
}

// TTS-7 : phrase sous le doigt (paragraphe EPUB, ligne PDF)
function sentenceContaining(units, k, idx) {
  const sents = sentencesOf(units[k]);
  const s = sents.findIndex(([, b]) => b > idx);
  return s >= 0 ? { u: k, s } : null;
}
function locatePoint(x, y) {
  return (units) => {
    const el = document.elementFromPoint(x, y);
    if (!el) return null;
    const page = el.closest('.page');
    if (page) {
      const k = +page.dataset.i, u = units[k];
      const ry = y - page.getBoundingClientRect().top;
      let best = null, bestD = Infinity;
      for (const p of u.parts) {
        const r = pdfItemRect(u.st, p.item, 0, p.item.str.length);
        const d = ry < r.top ? r.top - ry : ry > r.top + r.height ? ry - r.top - r.height : 0;
        if (d < bestD) { best = p; bestD = d; }
      }
      return best ? sentenceContaining(units, k, best.start) : null;
    }
    const sec = el.closest('.chapter');
    if (!sec) return null;
    const k = units.findIndex((u) => u.el === sec);
    const block = el.closest(BLOCK) || sec;
    const w = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) {
      const p = units[k].parts.find((q) => q.node === n);
      if (p && n.data.trim()) return sentenceContaining(units, k, p.start);
    }
    return null;
  };
}

function ttsPause() {
  if (tts.state !== 'playing') return;
  tts.token++;
  try { synth.cancel(); } catch {}
  setTtsState('paused');
  releaseWake();
  saveProgress();
}
function ttsResume() {
  if (tts.state !== 'paused') return;
  setTtsState('playing');
  requestWake();
  speakCurrent();
}
function ttsStop() {
  if (!tts.state) return;
  tts.token++;
  try { synth.cancel(); } catch {}
  setTtsState('');
  clearTtsHit();
  setSleep(null);
  releaseWake();
  saveProgress();
}
function ttsMove(dir) {
  const p = neighbour(dir);
  if (!p) return;
  tts.u = p.u; tts.s = p.s;
  if (tts.state === 'playing') speakCurrent(); else showSentence();
}

// TTS-8 : minuterie de sommeil
function setSleep(opt) {
  tts.sleepOpt = opt;
  tts.deadline = typeof opt === 'number' ? Date.now() + opt * 60000 : null;
  clearInterval(tts.sleepTimer);
  if (typeof opt === 'number') tts.sleepTimer = setInterval(updateSleepLabel, 1000);
  updateSleepLabel();
}
function updateSleepLabel() {
  const left = tts.sleepOpt === 'chapter' ? 'chapter' : tts.deadline ? tts.deadline - Date.now() : null;
  setText($('#ttsSleep'), Core.formatSleep(left));
}

$('#ttsBtn').addEventListener('click', () => ttsStartAt(locateTop));
$('#ttsPlay').addEventListener('click', () => (tts.state === 'playing' ? ttsPause() : ttsResume()));
$('#ttsStop').addEventListener('click', ttsStop);
$('#ttsNext').addEventListener('click', () => ttsMove(1));
$('#ttsPrev').addEventListener('click', () => ttsMove(-1));
$('#ttsSleep').addEventListener('click', () => setSleep(Core.nextSleepOption(tts.sleepOpt, !state.pdf)));
function setTtsRate(v) {
  settings.ttsRate = Core.clampTtsRate(v);
  saveSettings();
  $('#ttsRate').textContent = Core.formatRate(settings.ttsRate);
  if (tts.state === 'playing') speakCurrent();
}
$('#voiceSelect').addEventListener('change', (e) => {
  settings.ttsVoice = e.target.value || null;
  saveSettings();
  if (tts.state === 'playing') speakCurrent();
});
$('#ttsFaster').addEventListener('click', () => setTtsRate(settings.ttsRate + 0.1));
$('#ttsSlower').addEventListener('click', () => setTtsRate(settings.ttsRate - 0.1));

// TTS-7 : appui long (0,6 s, moins de 10 px de mouvement)
const press = { timer: null, x: 0, y: 0, id: null };
scroller.addEventListener('pointerdown', (e) => {
  if (!ttsSupported || (e.pointerType === 'mouse' && e.button !== 0) || e.target.closest('a')) return;
  clearTimeout(press.timer);
  press.x = e.clientX; press.y = e.clientY; press.id = e.pointerId;
  press.timer = setTimeout(() => {
    press.timer = null;
    window.LiseuseApp.longPresses++;
    state.suppressClick = true;
    setTimeout(() => { state.suppressClick = false; }, 1000);
    ttsStartAt(locatePoint(press.x, press.y));
  }, 600);
});
// Seul le doigt qui appuie compte (un second doigt, une souris ou un trackpad ne l'annulent pas)
scroller.addEventListener('pointermove', (e) => {
  if (e.pointerId !== press.id) return;
  if (press.timer && Math.hypot(e.clientX - press.x, e.clientY - press.y) > 10) { clearTimeout(press.timer); press.timer = null; }
});
['pointerup', 'pointercancel'].forEach((ev) => scroller.addEventListener(ev, (e) => {
  if (e.pointerId !== press.id) return;
  clearTimeout(press.timer); press.timer = null;
}));

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
  const theme = Core.effectiveTheme(settings, darkQuery.matches);
  document.documentElement.dataset.theme = theme;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim();
  const body = content.querySelector('.epub-body');
  if (body) {
    body.style.setProperty('--fs', settings.fontSize);
    body.classList.toggle('sans', settings.font === 'sans');
  }
  $('#fontVal').textContent = settings.fontSize;
  document.querySelectorAll('#themeSeg button').forEach((b) => b.classList.toggle('on', b.dataset.theme === theme));
  $('#autoTheme').checked = !!settings.autoTheme;
  $('#themePeriod').textContent = settings.autoTheme ? (darkQuery.matches ? '· de nuit' : '· de jour') : '';
  document.querySelectorAll('#fontSeg button').forEach((b) => b.classList.toggle('on', b.dataset.font === settings.font));
}
function changeLayout(fn) {
  const r = currentRatio();
  fn();
  saveSettings();
  applySettings();
  requestAnimationFrame(() => restoreRatio(r));
}
// AFF-10 : en mode automatique, choisir un thème remplace celui de la période en cours
document.querySelectorAll('#themeSeg button').forEach((b) => b.addEventListener('click', () => {
  const t = b.dataset.theme;
  if (settings.autoTheme) settings[darkQuery.matches ? 'nightTheme' : 'dayTheme'] = t;
  else settings.theme = t;
  saveSettings(); applySettings();
}));
$('#autoTheme').addEventListener('change', (e) => { settings.autoTheme = e.target.checked; saveSettings(); applySettings(); });
const onSchemeChange = () => { if (settings.autoTheme) applySettings(); };
if (darkQuery.addEventListener) darkQuery.addEventListener('change', onSchemeChange);
else if (darkQuery.addListener) darkQuery.addListener(onSchemeChange);
document.querySelectorAll('#fontSeg button').forEach((b) => b.addEventListener('click', () => changeLayout(() => { settings.font = b.dataset.font; })));
$('#fontDown').addEventListener('click', () => changeLayout(() => { settings.fontSize = Core.clampFontSize(settings.fontSize - 1); }));
$('#fontUp').addEventListener('click', () => changeLayout(() => { settings.fontSize = Core.clampFontSize(settings.fontSize + 1); }));

function closeSettings() { $('#settings').classList.add('hidden'); }
$('#settingsBtn').addEventListener('click', () => {
  pause();
  fillVoices();
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
let lastSize = `${document.documentElement.clientWidth}x${document.documentElement.clientHeight}`;
function onResize() {
  const size = `${document.documentElement.clientWidth}x${document.documentElement.clientHeight}`;
  if (size === lastSize) return; // AFF-12 : pas un vrai changement de taille
  lastSize = size;
  onRotate();
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

// AFF-13 : à la rotation, iOS peut garder un zoom ; réécrire la balise viewport réimpose l'échelle 1
const VIEWPORT = 'width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover';
let vpFlip = false;
function resetScale() {
  const m = document.querySelector('meta[name=viewport]');
  if (!m) return;
  vpFlip = !vpFlip; // contenu légèrement différent à chaque fois, pour qu'iOS le relise
  m.setAttribute('content', vpFlip ? VIEWPORT.replace('initial-scale=1', 'initial-scale=1.0') : VIEWPORT);
}
let rotTimer = null;
function onRotate() {
  resetScale();
  clearTimeout(rotTimer);
  rotTimer = setTimeout(resetScale, 500);
}
window.addEventListener('orientationchange', onRotate);
if (screen.orientation && screen.orientation.addEventListener) screen.orientation.addEventListener('change', onRotate);

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
  state.bookLang = wrap.lang;
  fillVoices();

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
      if (u) { el.setAttribute('decoding', 'async'); el.setAttribute('src', u); } else el.remove();
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
const APP_VERSION = 'v11'; // = numéro du cache dans sw.js (AFF-13)
$('#version').textContent = `Liseuse ${APP_VERSION}`;
window.LiseuseApp = { ready: false, lastSavedProgress: null, longPresses: 0 };
setSpeed(settings.speed);
applySettings();
renderLibrary().then(() => { window.LiseuseApp.ready = true; });
if (navigator.storage && navigator.storage.persist) navigator.storage.persist().catch(() => {});
if ('serviceWorker' in navigator && location.protocol !== 'file:') {
  navigator.serviceWorker.register('sw.js').catch(() => {});
}
