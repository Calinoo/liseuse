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

  const Core = {
    foldText, searchFolded, snippet, resultCount,
    locate, pageLabel,
    SPEED_MIN, SPEED_MAX, SPEED_DEFAULT, FONT_MIN, FONT_MAX,
    detectType, titleFromFilename, formatSize, dirOf, resolvePath, mimeOf, linkTarget,
    clampSpeed, speedStep, clampFontSize, progressRatio, remainingSeconds, formatRemaining,
  };

  if (typeof module === 'object' && module.exports) module.exports = Core;
  else root.LiseuseCore = Core;
})(this);
