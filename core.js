/* Logique pure de la Liseuse : aucune dépendance au DOM, entièrement testée
   (tests/test_core.py). Les identifiants renvoient à SPEC.md. */
(function (root) {
  'use strict';

  const SPEED_MIN = 5, SPEED_MAX = 200, SPEED_DEFAULT = 30;
  const FONT_MIN = 13, FONT_MAX = 34;

  // BIB-3
  function detectType(name, mime) {
    const m = /\.([^./]+)$/.exec(name || '');
    const ext = m ? m[1].toLowerCase() : '';
    if (ext === 'pdf') return 'pdf';
    if (ext === 'epub') return 'epub';
    if (ext) return null;
    if (/pdf/i.test(mime || '')) return 'pdf';
    if (/epub/i.test(mime || '')) return 'epub';
    return null;
  }

  // BIB-4
  function titleFromFilename(name) {
    return String(name).replace(/\.[^.]+$/, '');
  }

  // BIB-6
  function formatSize(n) {
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace('.', ',') + ' Mo';
    return Math.max(1, Math.round(n / 1e3)) + ' Ko';
  }

  // EPUB-2
  function dirOf(p) {
    const i = p.lastIndexOf('/');
    return i >= 0 ? p.slice(0, i + 1) : '';
  }

  function resolvePath(base, href) {
    href = String(href).split('#')[0].split('?')[0];
    try { href = decodeURIComponent(href); } catch (e) { /* encodage invalide : on garde tel quel */ }
    if (href.startsWith('/')) { base = ''; href = href.slice(1); }
    const out = [];
    for (const part of (base + href).split('/')) {
      if (part === '..') out.pop();
      else if (part && part !== '.') out.push(part);
    }
    return out.join('/');
  }

  function mimeOf(p) {
    const ext = (p.split('.').pop() || '').toLowerCase();
    return {
      jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
      svg: 'image/svg+xml', webp: 'image/webp',
    }[ext] || 'application/octet-stream';
  }

  // EPUB-4 / EPUB-5. ctx = { chapter, dir, index } ; index : chemin -> n° de chapitre
  function linkTarget(href, ctx) {
    href = String(href || '').trim();
    if (!href) return null;
    if (/^https?:/i.test(href)) return { type: 'external', url: href };
    if (/^[a-z][a-z0-9+.-]*:/i.test(href)) return null; // javascript:, mailto:, data:…
    const hash = href.indexOf('#');
    const frag = hash >= 0 ? href.slice(hash + 1) : '';
    let chapter;
    if (href.startsWith('#')) {
      chapter = ctx.chapter;
    } else {
      const path = resolvePath(ctx.dir, href);
      const idx = ctx.index instanceof Map ? ctx.index.get(path) : ctx.index[path];
      if (idx === undefined) return null;
      chapter = idx;
    }
    return { type: 'internal', id: frag ? `c${chapter}-${frag}` : `c${chapter}` };
  }

  // DEF-3
  function clampSpeed(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return SPEED_DEFAULT;
    return Math.max(SPEED_MIN, Math.min(SPEED_MAX, Math.round(n)));
  }

  function speedStep(v) {
    return v < 20 ? 1 : v < 60 ? 2 : 5;
  }

  // AFF-2
  function clampFontSize(v) {
    return Math.max(FONT_MIN, Math.min(FONT_MAX, Math.round(Number(v) || 19)));
  }

  // PROG-1
  function progressRatio(scrollTop, scrollHeight, clientHeight) {
    const max = scrollHeight - clientHeight;
    if (max <= 0) return 0;
    return Math.min(1, Math.max(0, scrollTop / max));
  }

  // PROG-5
  function remainingSeconds(scrollTop, scrollHeight, clientHeight, speed) {
    const left = scrollHeight - clientHeight - scrollTop;
    return left > 0 && speed > 0 ? left / speed : 0;
  }

  // PROG-6
  function formatRemaining(sec) {
    if (!(sec >= 0.5)) return 'Terminé';
    if (sec < 60) return '< 1 min';
    const min = Math.round(sec / 60);
    if (min < 60) return `~${min} min`;
    return `~${Math.floor(min / 60)} h ${String(min % 60).padStart(2, '0')}`;
  }

  // NAV-2 : indice de la dernière section/page dont le début est <= y (offsets triés)
  function locate(offsets, y) {
    if (!offsets.length) return -1;
    let lo = 0, hi = offsets.length - 1, ans = 0;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (offsets[mid] <= y) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans;
  }

  function pageLabel(i, n) {
    return `Page ${i + 1} / ${n}`;
  }

  // SRCH-2 : texte « replié » (minuscules, sans accents, apostrophes et espaces unifiés)
  // avec, pour chaque caractère replié, l'indice du caractère d'origine.
  const APOS = /[’‘ʼ`´]/;
  function foldText(text) {
    let out = '';
    const map = [];
    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      let f;
      if (/\s/.test(c)) {
        if (out.endsWith(' ')) continue;
        f = ' ';
      } else if (APOS.test(c)) {
        f = "'";
      } else {
        f = c.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
      }
      for (const ch of f) { out += ch; map.push(i); }
    }
    return { text: out, map };
  }

  function searchFolded(folded, query, max) {
    const q = foldText(String(query)).text.trim();
    if (q.length < 2) return [];
    const res = [];
    let i = folded.text.indexOf(q);
    while (i >= 0 && res.length < max) {
      res.push({ start: folded.map[i], end: folded.map[i + q.length - 1] + 1 });
      i = folded.text.indexOf(q, i + q.length);
    }
    return res;
  }

  // SRCH-3 : extrait autour d'un résultat
  function snippet(text, start, end, radius) {
    const ws = (s) => s.replace(/\s+/g, ' ');
    const b0 = Math.max(0, start - radius), a1 = Math.min(text.length, end + radius);
    let before = ws(text.slice(b0, start));
    let after = ws(text.slice(end, a1));
    if (b0 > 0) before = '…' + before.trimStart();
    if (a1 < text.length) after = after.trimEnd() + '…';
    return { before, match: ws(text.slice(start, end)), after };
  }

  function resultCount(n, max) {
    if (n === 0) return 'Aucun résultat';
    if (n > max) return `${max}+ résultats`;
    return n === 1 ? '1 résultat' : `${n} résultats`;
  }

  // AFF-1 / AFF-10 : thèmes et thème effectif
  const THEMES = ['light', 'sepia', 'green', 'dark', 'night', 'amber'];
  function effectiveTheme(s, dark) {
    const ok = (t, d) => (THEMES.includes(t) ? t : d);
    if (s.autoTheme) return dark ? ok(s.nightTheme, 'night') : ok(s.dayTheme, 'light');
    return ok(s.theme, 'light');
  }

  // AFF-9 : contraste WCAG 2
  function parseColor(c) {
    c = String(c).trim();
    let m = /^#([0-9a-f]{6})$/i.exec(c);
    if (m) return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
    m = /^rgba?\(([^)]+)\)$/i.exec(c);
    if (m) return m[1].split(',').slice(0, 3).map((x) => Math.round(parseFloat(x)));
    return null;
  }
  function luminance(rgb) {
    const [r, g, b] = rgb.map((v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  }
  function contrastRatio(a, b) {
    const la = luminance(parseColor(a)), lb = luminance(parseColor(b));
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  }

  // TTS-2 : découpage en phrases (indices [début, fin) dans le texte d'origine)
  const ABBR = new Set(['m', 'mme', 'mlle', 'mm', 'dr', 'pr', 'st', 'ste', 'etc', 'cf', 'p', 'pp', 'vol',
    'chap', 'av', 'apr', 'env', 'fig', 'no', 'n°', 'jr', 'sr', 'mr', 'mrs', 'ms', 'vs']);
  const ENDP = /[.!?…]/, CLOSE = /[»"”’)\]]/, WS = /\s/;
  const STARTER = /[\p{Lu}\p{N}«“"—–\-¿¡]/u;
  function splitSentences(text, maxLen, breaks) {
    maxLen = maxLen || 250;
    const bset = new Set(breaks || []);
    const raw = [];
    const push = (a, b) => {
      while (a < b && WS.test(text[a])) a++;
      while (b > a && WS.test(text[b - 1])) b--;
      if (b > a) raw.push([a, b]);
    };
    let start = 0;
    for (let i = 0; i < text.length; i++) {
      if (bset.has(i) && i > start) { push(start, i); start = i; }
      if (!ENDP.test(text[i])) continue;
      let j = i;
      while (j + 1 < text.length && ENDP.test(text[j + 1])) j++;
      if (text[i] === '.' && j === i) {
        const w = /([\p{L}°]+)$/u.exec(text.slice(start, i));
        if (w && ((w[1].length === 1 && /\p{Lu}/u.test(w[1])) || ABBR.has(w[1].toLowerCase()))) { i = j; continue; }
      }
      let k = j + 1, end = j + 1, sawSpace = false;
      while (k < text.length && !bset.has(k) && (WS.test(text[k]) || CLOSE.test(text[k]))) {
        if (WS.test(text[k])) sawSpace = true; else end = k + 1;
        k++;
      }
      const isEnd = k >= text.length || bset.has(k) || ((sawSpace || end > j + 1) && STARTER.test(text[k]));
      if (!isEnd || (!sawSpace && k < text.length && !bset.has(k) && end === j + 1)) { i = j; continue; }
      push(start, end);
      start = end;
      i = end - 1;
    }
    push(start, text.length);
    // Découpe des phrases trop longues
    const out = [];
    for (let [a, b] of raw) {
      while (b - a > maxLen) {
        const win = text.slice(a, a + maxLen);
        let cut = -1;
        for (let p = win.length - 1; p > maxLen * 0.3; p--) {
          if (/[,;:]/.test(win[p]) && (p + 1 >= win.length || WS.test(text[a + p + 1]))) { cut = a + p + 1; break; }
        }
        if (cut < 0) { const sp = win.lastIndexOf(' '); cut = sp > 0 ? a + sp : a + maxLen; }
        let e = cut;
        while (e > a && WS.test(text[e - 1])) e--;
        out.push([a, e]);
        a = cut;
        while (a < b && WS.test(text[a])) a++;
      }
      if (b > a) out.push([a, b]);
    }
    return out;
  }

  // TTS-3 : choix de la voix (région demandée d'abord, puis qualité)
  const QUALITY = /premium|enhanced|amélioré|neural|natural/i;
  const DEFAULT_REGION = { fr: 'FR', en: 'US', es: 'ES', de: 'DE', it: 'IT', pt: 'PT', nl: 'NL' };
  function pickVoice(voices, lang) {
    if (!voices || !voices.length) return null;
    const [b, r] = String(lang || 'fr').replace('_', '-').split('-');
    const base = b.toLowerCase(), region = (r || DEFAULT_REGION[base] || '').toUpperCase();
    let best = null, bestScore = -1;
    for (const v of voices) {
      const [vb, vr] = String(v.lang || '').replace('_', '-').split('-');
      if ((vb || '').toLowerCase() !== base) continue;
      const score = 10 + ((vr || '').toUpperCase() === region ? 5 : 0) + (QUALITY.test(v.name) ? 3 : 0)
        + (v.localService ? 1 : 0) + (v.default ? 0.5 : 0);
      if (score > bestScore) { best = v; bestScore = score; }
    }
    if (!best) best = voices.find((v) => v.default) || voices[0];
    return best.name;
  }

  // TTS-6 : vitesse de la voix
  function clampTtsRate(v) {
    const n = Number(v);
    if (!Number.isFinite(n)) return 1;
    return Math.round(Math.max(0.5, Math.min(2, n)) * 10) / 10;
  }
  function formatRate(v) { return v.toFixed(1).replace('.', ',') + '×'; }

  // TTS-8 : minuterie de sommeil
  function nextSleepOption(cur, hasChapters) {
    const opts = [null, 15, 30, 60];
    if (hasChapters) opts.push('chapter');
    const i = opts.indexOf(cur);
    return opts[(i + 1) % opts.length];
  }
  function formatSleep(left) {
    if (left === null || left === undefined) return '⏲';
    if (left === 'chapter') return 'Fin chap.';
    return Math.max(0, Math.ceil(left / 60000)) + ' min';
  }

  const Core = {
    splitSentences, pickVoice, clampTtsRate, formatRate, nextSleepOption, formatSleep,
    THEMES, effectiveTheme, parseColor, contrastRatio,
    foldText, searchFolded, snippet, resultCount,
    locate, pageLabel,
    SPEED_MIN, SPEED_MAX, SPEED_DEFAULT, FONT_MIN, FONT_MAX,
    detectType, titleFromFilename, formatSize, dirOf, resolvePath, mimeOf, linkTarget,
    clampSpeed, speedStep, clampFontSize, progressRatio, remainingSeconds, formatRemaining,
  };

  if (typeof module === 'object' && module.exports) module.exports = Core;
  else root.LiseuseCore = Core;
})(this);
