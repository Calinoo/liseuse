"""Actions utilisateur réutilisables pour les tests de bout en bout."""
import re

SCROLL = "document.getElementById('scroller')"


def import_books(page, books, *names, expect_count=None):
    """Importe des fichiers via le vrai sélecteur et attend la fin de l'import."""
    before = page.locator(".book").count()
    page.set_input_files("#fileInput", [books(n) for n in names])
    expected = before + len(names) if expect_count is None else expect_count
    page.wait_for_function(f"document.querySelectorAll('.book').length === {expected}"
                           " && document.getElementById('loading').classList.contains('hidden')")


def open_book(page, title):
    page.locator(".book", has_text=title).first.locator(".title").click()
    page.wait_for_selector("#readerView:not(.hidden)")
    page.wait_for_function("document.getElementById('loading').classList.contains('hidden')")


def wait_dialog(page, text, timeout=10_000):
    """Attend qu'un alert/confirm contenant `text` ait été affiché."""
    waited = 0
    while not any(text in d for d in page.dialogs):
        assert waited < timeout, f"aucun message contenant {text!r} (reçus : {page.dialogs})"
        page.wait_for_timeout(50)
        waited += 50


def back_to_library(page):
    page.locator("#backBtn").click()
    page.wait_for_selector("#library:not(.hidden)")
    page.wait_for_function("document.querySelectorAll('.book').length > 0")


def scroll_top(page):
    return page.evaluate(f"{SCROLL}.scrollTop")


def set_scroll(page, top):
    page.evaluate(f"t => {{ {SCROLL}.scrollTop = t; {SCROLL}.dispatchEvent(new Event('scroll')); }}", top)


def set_ratio(page, r):
    page.evaluate(f"r => {{ const s = {SCROLL}; s.scrollTop = r * (s.scrollHeight - s.clientHeight);"
                  " s.dispatchEvent(new Event('scroll')); }", r)


def ratio(page):
    return page.evaluate(f"(() => {{ const s = {SCROLL}; return s.scrollTop / (s.scrollHeight - s.clientHeight); }})()")


def tap_text(page):
    """Toucher le texte (hors lien)."""
    page.dispatch_event("#scroller", "click")


def is_playing(page):
    return page.locator("#playBtn").get_attribute("aria-label") == "Pause"


def bars_hidden(page):
    return page.evaluate("document.getElementById('readerView').classList.contains('bars-hidden')")


def pct_text(page):
    return page.locator("#pct").inner_text()


def remaining_text(page):
    return page.locator("#remaining").inner_text()


def library_titles(page):
    return page.locator(".book .title").all_inner_texts()


def stored_books(page):
    """Lit IndexedDB directement (vérifie la persistance réelle)."""
    return page.evaluate("""() => new Promise((res, rej) => {
        const r = indexedDB.open('liseuse');
        r.onsuccess = () => {
            const q = r.result.transaction('books').objectStore('books').getAll();
            q.onsuccess = () => { res(q.result); r.result.close(); };
            q.onerror = () => rej(q.error);
        };
        r.onerror = () => rej(r.error);
    })""")


def install_clock(page):
    """Fige l'horloge simulée (installée avant le chargement par la fixture `app`) :
    le temps n'avance plus que via page.clock.run_for(ms), ce qui rend les mesures exactes
    même quand la machine est chargée."""
    page.clock.pause_at(page.evaluate("Date.now()") + 1)


NUM = re.compile(r"\d+")
