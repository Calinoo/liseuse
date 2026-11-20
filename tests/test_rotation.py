"""AFF-13 : rien ne dépasse de l'écran, en portrait comme en paysage.

Sur iPhone, si un élément dépasse la largeur de l'écran, iOS dézoome la page à la rotation ;
avec le zoom bloqué (AFF-12), l'app resterait coincée dans ce zoom.
"""
import pytest

from helpers import import_books, open_book

OVERFLOW = """() => {
  const W = document.documentElement.clientWidth;
  const bad = [];
  if (document.documentElement.scrollWidth > W + 1) bad.push('document ' + document.documentElement.scrollWidth + '>' + W);
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('#content')) continue;            // le texte du livre défile dans son cadre
    const r = el.getBoundingClientRect();
    if (!r.width || getComputedStyle(el).visibility === 'hidden') continue;
    if (r.right > W + 1 || r.left < -1) bad.push((el.id || el.className || el.tagName) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + '/' + W);
  }
  return bad;
}"""


def check(page, where):
    bad = page.evaluate(OVERFLOW)
    assert bad == [], f"{where} : {bad}"


def landscape(page):
    vp = page.viewport_size
    return {"width": max(vp["width"], vp["height"]), "height": min(vp["width"], vp["height"])}


@pytest.mark.parametrize("orient", ["portrait", "paysage"])
def test_AFF13_nothing_wider_than_screen(app, books, orient):
    if orient == "paysage":
        app.set_viewport_size(landscape(app))
        app.wait_for_timeout(400)
    import_books(app, books, "sample.epub", "long.pdf")
    check(app, "bibliothèque")
    open_book(app, "Mon livre de test")
    check(app, "lecteur")
    app.locator("#settingsBtn").click()
    check(app, "panneau Aa")
    app.locator("#settingsBtn").click()
    app.locator("#searchBtn").click()
    check(app, "recherche")
    app.locator("#searchClose").click()
    if app.locator("#ttsBtn").is_visible():
        app.locator("#ttsBtn").click()
        check(app, "commandes de la voix")


def test_AFF13_rotation_back_and_forth_keeps_app_usable(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    port = app.viewport_size
    for size in (landscape(app), port, landscape(app), port):
        app.set_viewport_size(size)
        app.wait_for_timeout(400)
        check(app, f"{size}")
    app.locator("#settingsBtn").click()
    assert app.locator("#settings").is_visible(), "l'app doit encore répondre"


def test_AFF13_rotation_reasserts_scale_1(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    app.evaluate("""() => { window.__vp = 0; const m = document.querySelector('meta[name=viewport]');
        new MutationObserver(() => window.__vp++).observe(m, { attributes: true }); }""")
    vp = app.viewport_size
    app.set_viewport_size(landscape(app))
    app.wait_for_timeout(800)
    assert app.evaluate("window.__vp") >= 1, "la balise viewport doit être réécrite à la rotation"
    content = app.locator("meta[name=viewport]").get_attribute("content")
    assert "initial-scale=1" in content and "maximum-scale=1" in content
    app.set_viewport_size(vp)


ZOOMED = """() => { Object.defineProperty(window.visualViewport, 'scale', { configurable: true, get: () => %s }); }"""
FIRE = """() => {
  const g = new Event('gesturestart', { cancelable: true, bubbles: true });
  document.body.dispatchEvent(g);
  const t = new Event('touchmove', { cancelable: true, bubbles: true });
  Object.defineProperty(t, 'touches', { value: [{ clientX: 10, clientY: 10 }, { clientX: 90, clientY: 90 }] });
  document.body.dispatchEvent(t);
  return [g.defaultPrevented, t.defaultPrevented];
}"""


def test_AFF13_stuck_zoom_can_be_undone(app):
    app.evaluate(ZOOMED % "1")
    assert app.evaluate(FIRE) == [True, True]          # normal : l'app ne zoome pas
    app.evaluate(ZOOMED % "1.6")
    assert app.evaluate(FIRE) == [False, False]        # coincée en zoom : on laisse dézoomer


def test_AFF13_version_shown_matches_cache(app):
    import os
    import re
    sw = open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "sw.js"), encoding="utf-8").read()
    cache = re.search(r"liseuse-(v\d+)", sw).group(1)
    assert app.locator("#version").inner_text().strip().endswith(cache)
