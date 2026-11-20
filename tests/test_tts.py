"""Lecture à voix haute : TTS-1 à TTS-10.

Les navigateurs de test n'ont pas de vraie voix : on remplace la synthèse vocale par
une doublure qui enregistre chaque phrase prononcée. Le test décide quand une phrase
est terminée (__ttsFinish), ce qui rend tout exact et reproductible.
"""
import pytest

from helpers import import_books, open_book, set_scroll, set_ratio, scroll_top, tap_text, is_playing, SCROLL

STUB = """
(() => {
  const log = window.__tts = { spoken: [], current: null, cancels: 0 };
  class U { constructor(t) { this.text = t; this.rate = 1; this.voice = null; this.lang = ''; } }
  const voices = [
    { name: 'Thomas', lang: 'fr-FR', localService: true, default: true },
    { name: 'Amélie (Améliorée)', lang: 'fr-CA', localService: true },
    { name: 'Audrey (Premium)', lang: 'fr-FR', localService: true },
    { name: 'Samantha', lang: 'en-US', localService: true },
    { name: 'Eddy', lang: 'fr-FR', voiceURI: 'com.apple.eloquence.fr-FR.Eddy', localService: true },
  ];
  const synth = {
    speaking: false, paused: false, pending: false,
    getVoices: () => voices,
    speak(u) {
      log.spoken.push({ text: u.text, rate: u.rate, voice: u.voice && u.voice.name, lang: u.lang });
      log.current = u; this.speaking = true;
      if (u.onstart) setTimeout(() => u.onstart({}), 0);
    },
    cancel() {
      log.cancels++; const u = log.current; log.current = null; this.speaking = false;
      if (u && u.onerror) setTimeout(() => u.onerror({ error: 'interrupted' }), 0);
    },
    pause() { this.paused = true; }, resume() { this.paused = false; },
    addEventListener() {}, removeEventListener() {},
  };
  Object.defineProperty(window, 'speechSynthesis', { configurable: true, value: synth });
  window.SpeechSynthesisUtterance = U;
  window.__ttsFinish = () => { const u = log.current; log.current = null; synth.speaking = false;
                               if (u && u.onend) u.onend({}); };
  window.__wake = [];
  Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
      request: async (t) => { window.__wake.push('request');
          return { release: async () => window.__wake.push('release') }; } } });
})();
"""


@pytest.fixture
def tts(ctx, base_url, books):
    page = ctx.new_page()
    page.dialogs = []
    page.on("dialog", lambda d: (page.dialogs.append(d.message), d.accept()))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(STUB)
    # Horloge simulée installée AVANT le chargement : sinon, sous forte charge, des minuteurs
    # de l'app peuvent être créés sur l'horloge réelle (test instable constaté en parallèle).
    page.clock.install()
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    yield page
    assert errors == [], errors


def open_epub(page, books):
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")


def spoken(page):
    return [s["text"] for s in page.evaluate("window.__tts.spoken")]


def last_spoken(page):
    return page.evaluate("window.__tts.spoken.at(-1)")


def finish(page, n=1):
    for _ in range(n):
        page.evaluate("window.__ttsFinish()")


def state(page):
    return page.evaluate("document.getElementById('readerView').dataset.tts || ''")


def long_press(page, selector, ms=700, move=0, y_frac=0.5):
    # comme un vrai doigt : on appuie sur du texte visible à l'écran
    page.evaluate("s => document.querySelector(s).scrollIntoView({ block: 'center' })", selector)
    box = page.locator(selector).first.bounding_box()
    x, y = box["x"] + min(40, box["width"] / 2), box["y"] + box["height"] * y_frac
    page.dispatch_event("#scroller", "pointerdown", {"clientX": x, "clientY": y, "pointerType": "touch",
                                                    "isPrimary": True, "pointerId": 7})
    if move:
        page.dispatch_event("#scroller", "pointermove", {"clientX": x, "clientY": y + move,
                                                        "pointerType": "touch", "pointerId": 7})
    before = page.evaluate("window.LiseuseApp.longPresses")
    page.clock.run_for(ms)
    if ms >= 600 and not move:
        # Doigt maintenu jusqu'à ce que l'app reconnaisse l'appui long (sous forte charge,
        # l'horloge simulée de Playwright peut prendre du retard sur les minuteurs).
        for _ in range(60):
            if page.evaluate("window.LiseuseApp.longPresses") > before:
                break
            page.clock.run_for(50)
            page.wait_for_timeout(25)
        assert page.evaluate("window.LiseuseApp.longPresses") > before, "appui long non reconnu"
        for _ in range(40):   # démarrage asynchrone de la lecture
            if page.evaluate("document.getElementById('readerView').dataset.tts"):
                break
            page.wait_for_timeout(25)
    else:
        assert page.evaluate("window.LiseuseApp.longPresses") == before, "un appui court a été pris pour un appui long"
    page.dispatch_event("#scroller", "pointerup", {"clientX": x, "clientY": y + move,
                                                  "pointerType": "touch", "pointerId": 7})
    page.diag = page.evaluate("""([x, y, sel]) => { const e = document.elementFromPoint(x, y);
        const r = document.querySelector(sel).getBoundingClientRect();
        return { under: e && (e.id || e.className || e.tagName), x, y, boxNow: [r.top, r.bottom],
                 spoken: window.__tts.spoken.length, tts: document.getElementById('readerView').dataset.tts,
                 loading: !document.getElementById('loading').classList.contains('hidden') }; }""", [x, y, selector])


def hit_top(page):
    return page.evaluate("(() => { const h = document.querySelector('.tts-hit');"
                         " return h ? h.getBoundingClientRect().top : null; })()")


# ---------- TTS-1 ----------
def test_TTS1_button_starts_from_top_of_screen(tts, books):
    open_epub(tts, books)
    assert tts.locator("#ttsBtn").is_visible()
    tts.locator("#ttsBtn").click()
    assert state(tts) == "playing"
    assert spoken(tts) == ["Chapitre 1"]
    set_ratio(tts, 0.5)
    tts.locator("#ttsStop").click()
    tts.locator("#ttsBtn").click()
    top = hit_top(tts)
    bar = tts.locator("#topBar").bounding_box()
    h = tts.viewport_size["height"]
    assert top is not None and bar["y"] + bar["height"] - 40 <= top <= 0.6 * h, top


def test_TTS1_hidden_without_speech_synthesis(ctx, base_url, books):
    page = ctx.new_page()
    page.add_init_script("delete window.speechSynthesis; Object.defineProperty(window, 'speechSynthesis',"
                         " { value: undefined, configurable: true });")
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_epub(page, books)
    assert not page.locator("#ttsBtn").is_visible()


# ---------- TTS-2 ----------
def test_TTS2_reads_on_sentence_by_sentence(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    finish(tts, 3)
    said = spoken(tts)
    assert said[0] == "Chapitre 1"
    assert said[1].startswith("Aller à la fin")        # le titre n'est pas fusionné
    assert all(len(s) <= 250 for s in said)


def test_TTS2_crosses_chapters_and_stops_at_end(tts, books):
    open_epub(tts, books)
    long_press(tts, "#c0-note1")
    assert spoken(tts) == ["Note 1."], repr(sorted(tts.diag.items()))
    finish(tts)
    assert spoken(tts)[-1] == "Chapitre 2"
    long_press(tts, "#c2-fin")
    assert spoken(tts)[-1] == "Fin du livre.", repr(sorted(tts.diag.items()))
    n = len(spoken(tts))
    finish(tts)
    assert len(spoken(tts)) == n and state(tts) == ""
    assert tts.locator(".tts-hit").count() == 0


def test_TTS2_long_sentence_is_split(tts, books):
    open_epub(tts, books)
    long_press(tts, "#c1-longue")
    finish(tts, 3)
    parts = [s for s in spoken(tts) if "virgules" in s or "très longue" in s or "termine enfin" in s]
    assert len(parts) >= 2 and all(len(p) <= 250 for p in parts)
    assert parts[-1].endswith("se termine enfin ici.")


# ---------- TTS-3 ----------
def test_TTS3_best_french_voice(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    u = last_spoken(tts)
    assert u["voice"] == "Audrey (Premium)" and u["lang"].startswith("fr")


def test_TTS11_choose_voice_applies_now_and_is_remembered(tts, books):
    open_epub(tts, books)
    tts.locator("#settingsBtn").click()
    sel = tts.locator("#voiceSelect")
    assert sel.is_visible()
    labels = sel.locator("option").all_inner_texts()
    assert labels[0].startswith("Automatique") and "Eddy" not in " ".join(labels)
    assert labels[1:] == ["Audrey · Premium", "Thomas", "Amélie · Améliorée (Canada)"]
    assert "Contenu énoncé" in tts.locator("#voiceHint").inner_text()
    tts.locator("#settingsBtn").click()
    tts.locator("#ttsBtn").click()
    n = len(spoken(tts))
    tts.locator("#settingsBtn").click()
    sel.select_option("Thomas")
    u = last_spoken(tts)
    assert len(spoken(tts)) == n + 1 and u["voice"] == "Thomas" and u["text"] == "Chapitre 1"
    tts.reload()
    tts.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(tts, "Mon livre de test")
    assert tts.locator("#voiceSelect").input_value() == "Thomas"
    tts.locator("#ttsBtn").click()
    assert last_spoken(tts)["voice"] == "Thomas"


def test_TTS11_no_voice_choice_without_synthesis(ctx, base_url, books):
    page = ctx.new_page()
    page.add_init_script("delete window.speechSynthesis; Object.defineProperty(window, 'speechSynthesis',"
                         " { configurable: true, value: undefined });")
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_epub(page, books)
    page.locator("#settingsBtn").click()
    assert not page.locator("#voiceSelect").is_visible()


# ---------- TTS-4 ----------
def test_TTS4_highlight_and_follow(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    assert tts.locator(".tts-hit").count() >= 1
    h = tts.viewport_size["height"]
    for _ in range(25):
        finish(tts)
        tts.clock.run_for(500)
        top = hit_top(tts)
        assert 0.1 * h <= top <= 0.65 * h, f"phrase hors zone : {top} / {h}"


def test_TTS4_manual_scroll_suspends_follow(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    tts.dispatch_event("#scroller", "touchstart")
    set_scroll(tts, 3000)
    tts.dispatch_event("#scroller", "touchend")
    finish(tts)
    tts.clock.run_for(500)
    assert scroll_top(tts) == pytest.approx(3000, abs=2), "le suivi doit attendre"
    tts.clock.run_for(3000)
    finish(tts)
    tts.clock.run_for(500)
    assert scroll_top(tts) < 1500, "le suivi doit reprendre après 3 s"


# ---------- TTS-5 ----------
def test_TTS5_controls(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    finish(tts, 2)
    current = spoken(tts)[-1]
    tts.locator("#ttsPlay").click()                 # pause
    assert state(tts) == "paused"
    tap_text(tts)                                    # toucher = reprise
    assert state(tts) == "playing" and spoken(tts)[-1] == current
    tts.locator("#ttsNext").click()
    nxt = spoken(tts)[-1]
    assert nxt != current
    tts.locator("#ttsPrev").click()
    assert spoken(tts)[-1] == current
    tts.locator("#ttsStop").click()
    assert state(tts) == "" and tts.locator(".tts-hit").count() == 0
    assert tts.locator("#playBtn").is_visible() and not tts.locator("#ttsPlay").is_visible()


def test_TTS5_voice_and_autoscroll_exclude_each_other(tts, books):
    open_epub(tts, books)
    tts.locator("#playBtn").click()
    assert is_playing(tts)
    tts.locator("#ttsBtn").click()
    assert not is_playing(tts) and state(tts) == "playing"
    tts.locator("#ttsStop").click()
    tts.locator("#ttsBtn").click()
    # relancer le défilement automatique arrête la voix
    tts.evaluate("document.getElementById('playBtn').click()")
    assert state(tts) == "" and is_playing(tts)


# ---------- TTS-6 ----------
def test_TTS6_rate_applies_now_and_is_remembered(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    for _ in range(3):
        tts.locator("#ttsFaster").click()
    assert tts.locator("#ttsRate").inner_text() == "1,3×"
    u = last_spoken(tts)
    assert u["rate"] == pytest.approx(1.3) and u["text"] == "Chapitre 1"
    for _ in range(20):
        tts.locator("#ttsSlower").click()
    assert tts.locator("#ttsRate").inner_text() == "0,5×"
    tts.reload()
    tts.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(tts, "Mon livre de test")
    tts.locator("#ttsBtn").click()
    assert tts.locator("#ttsRate").inner_text() == "0,5×"
    assert last_spoken(tts)["rate"] == pytest.approx(0.5)


# ---------- TTS-7 ----------
def test_TTS7_long_press_reads_from_paragraph_and_is_not_a_tap(tts, books):
    open_epub(tts, books)
    long_press(tts, "#c0-note1")
    assert spoken(tts) == ["Note 1."] and state(tts) == "playing"
    tap_text(tts)  # le « click » qui suit un appui long est ignoré
    assert state(tts) == "playing"
    assert not is_playing(tts)


@pytest.mark.parametrize("ms, move", [(300, 0), (700, 30)])
def test_TTS7_short_or_moving_press_does_nothing(tts, books, ms, move):
    open_epub(tts, books)
    long_press(tts, "#c0-note1", ms=ms, move=move)
    assert spoken(tts) == [] and state(tts) == ""


def test_TTS7_no_ios_selection_menu_in_reader(tts, books):
    open_epub(tts, books)
    css = tts.evaluate("(() => { const s = getComputedStyle(document.getElementById('content'));"
                       " return [s.webkitUserSelect || s.userSelect, s.webkitTouchCallout || 'none']; })()")
    assert css[0] == "none" and css[1] == "none"


def test_TTS7_long_press_on_pdf_line(tts, books):
    import_books(tts, books, "long.pdf")
    open_book(tts, "long")
    set_ratio(tts, 0.07)
    tts.clock.run_for(300)
    # ligne 10 de la page 3 : ligne de base à y = 740 - 9*22 = 542 (repère PDF, origine en bas)
    y_frac = (842 - 542 - 5) / 842
    long_press(tts, '.page[data-i="2"]', y_frac=y_frac)
    # un PDF demande d'extraire d'abord le texte de toutes ses pages
    for _ in range(100):
        if spoken(tts):
            break
        tts.clock.run_for(100)
        tts.wait_for_timeout(50)
    assert spoken(tts)[0].startswith("Ligne 10 de la page 3")


# ---------- TTS-8 ----------
def test_TTS8_timer_cycles_and_stops_after_sentence(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    btn = tts.locator("#ttsSleep")
    labels = [btn.inner_text()]
    for _ in range(5):
        btn.click()
        labels.append(btn.inner_text())
    assert labels == ["⏲", "15 min", "30 min", "60 min", "Fin chap.", "⏲"]
    btn.click()                                    # 15 min
    tts.clock.run_for(5 * 60_000)
    assert btn.inner_text() == "10 min"
    tts.clock.run_for(10 * 60_000 + 1000)
    n = len(spoken(tts))
    assert state(tts) == "playing"                 # la phrase en cours n'est pas coupée
    finish(tts)
    assert len(spoken(tts)) == n and state(tts) == ""


def test_TTS8_end_of_chapter(tts, books):
    open_epub(tts, books)
    long_press(tts, "#c0-note1")
    for _ in range(4):
        tts.locator("#ttsSleep").click()
    assert tts.locator("#ttsSleep").inner_text() == "Fin chap."
    finish(tts)
    assert spoken(tts) == ["Note 1."] and state(tts) == ""


def test_TTS8_no_chapter_option_for_pdf(tts, books):
    import_books(tts, books, "sample.pdf")
    open_book(tts, "sample")
    tts.locator("#ttsBtn").click()
    labels = []
    for _ in range(4):
        tts.locator("#ttsSleep").click()
        labels.append(tts.locator("#ttsSleep").inner_text())
    assert labels == ["15 min", "30 min", "60 min", "⏲"]


# ---------- TTS-9 ----------
def test_TTS9_screen_awake_and_pause_in_background(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    tts.wait_for_function("window.__wake.includes('request')")
    finish(tts)
    current = spoken(tts)[-1]
    tts.evaluate("""() => {
        Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    assert state(tts) == "paused"
    tts.evaluate("Object.defineProperty(document, 'hidden', { configurable: true, get: () => false })")
    tts.locator("#ttsPlay").click()
    assert state(tts) == "playing" and spoken(tts)[-1] == current


# ---------- TTS-10 ----------
def test_TTS10_scanned_pdf(tts, books):
    import_books(tts, books, "scan.pdf")
    open_book(tts, "scan")
    tts.locator("#ttsBtn").click()
    tts.wait_for_function("document.getElementById('readerView').dataset.tts !== 'playing'")
    waited = 0
    while not any("pas de texte à lire" in d for d in tts.dialogs) and waited < 5000:
        tts.wait_for_timeout(50)
        waited += 50
    assert any("pas de texte à lire" in d for d in tts.dialogs)


def test_TTS10_progress_saved_while_reading(tts, books):
    open_epub(tts, books)
    tts.locator("#ttsBtn").click()
    finish(tts, 30)
    tts.wait_for_function("window.LiseuseApp.lastSavedProgress > 0.02", timeout=5000)


def test_TTS7_other_pointer_does_not_cancel_long_press(tts, books):
    """Un mouvement d'un autre pointeur (souris, trackpad, 2e doigt) n'annule pas l'appui long."""
    open_epub(tts, books)
    tts.evaluate("document.querySelector('#c0-note1').scrollIntoView({ block: 'center' })")
    box = tts.locator("#c0-note1").bounding_box()
    x, y = box["x"] + 30, box["y"] + box["height"] / 2
    tts.dispatch_event("#scroller", "pointerdown", {"clientX": x, "clientY": y, "pointerType": "touch",
                                                   "isPrimary": True, "pointerId": 7})
    tts.dispatch_event("#scroller", "pointermove", {"clientX": 0, "clientY": 0, "pointerType": "mouse",
                                                   "pointerId": 1})
    tts.clock.run_for(700)
    tts.dispatch_event("#scroller", "pointerup", {"clientX": x, "clientY": y, "pointerType": "touch",
                                                 "pointerId": 7})
    assert spoken(tts) == ["Note 1."]
