"""Pincement à deux doigts : AFF-12.

WebKit (Playwright) ne sait pas fabriquer de vrais événements tactiles : on envoie des
événements « touch* » dont la liste `touches` donne la position des deux doigts, comme iOS.
"""
import pytest

from helpers import import_books, open_book, set_ratio, ratio, is_playing, SCROLL

PINCH = """([scale, steps]) => {
  const el = document.getElementById('scroller');
  const r = el.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  const fire = (type, d) => {
    const touches = d == null ? [] : [{ identifier: 1, clientX: cx - d / 2, clientY: cy },
                                       { identifier: 2, clientX: cx + d / 2, clientY: cy }];
    const e = new Event(type, { bubbles: true, cancelable: true });
    Object.defineProperty(e, 'touches', { value: touches });
    el.dispatchEvent(e);
    return e.defaultPrevented;
  };
  fire('touchstart', 100);
  let prevented = true;
  for (let i = 1; i <= steps; i++) prevented = fire('touchmove', 100 + (100 * scale - 100) * i / steps) && prevented;
  fire('touchend', null);
  return prevented;
}"""


def pinch(page, scale, steps=6):
    return page.evaluate(PINCH, [scale, steps])


def settle(page):
    page.wait_for_timeout(400)


def test_AFF12_app_itself_never_zooms(app):
    assert "maximum-scale=1" in app.locator("meta[name=viewport]").get_attribute("content")
    assert app.evaluate("""() => { const e = new Event('gesturestart', { cancelable: true, bubbles: true });
                                   document.body.dispatchEvent(e); return e.defaultPrevented; }""")


def test_AFF12_pinch_changes_epub_text_size(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    set_ratio(app, 0.4)
    settle(app)
    assert app.locator("#fontVal").inner_text() == "19"
    pinch(app, 1.5)
    settle(app)
    assert app.locator("#fontVal").inner_text() == "29"
    assert app.evaluate("getComputedStyle(document.querySelector('.epub-body')).getPropertyValue('--fs').trim()") == "29"
    assert ratio(app) == pytest.approx(0.4, abs=0.01)
    assert not is_playing(app), "un pincement n'est pas un toucher"
    assert app.evaluate("window.LiseuseApp.longPresses") == 0
    pinch(app, 0.5)
    settle(app)
    assert app.locator("#fontVal").inner_text() == "15"
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(app, "Mon livre de test")
    assert app.locator("#fontVal").inner_text() == "15"


def page_metrics(page):
    return page.evaluate(f"""(() => {{ const s = {SCROLL}, p = document.querySelector('.page');
        const c = document.querySelector('.page canvas');
        return {{ pw: p.getBoundingClientRect().width, sw: s.clientWidth, scrollW: s.scrollWidth,
                  canvas: c ? c.width : 0 }}; }})()""")


def test_AFF12_pinch_zooms_pdf_pages(app, books):
    import_books(app, books, "long.pdf")
    open_book(app, "long")
    set_ratio(app, 0.4)
    app.wait_for_function("document.querySelector('.page canvas')")
    before = page_metrics(app)
    assert before["scrollW"] <= before["sw"] + 1
    pinch(app, 2)
    settle(app)
    app.wait_for_function("document.querySelector('.page canvas')")
    after = page_metrics(app)
    assert after["pw"] == pytest.approx(2 * before["pw"], rel=0.02)
    assert after["scrollW"] > after["sw"] * 1.5, "on doit pouvoir glisser de côté"
    assert ratio(app) == pytest.approx(0.4, abs=0.01)
    app.wait_for_function(f"(() => {{ const c = document.querySelector('.page canvas');"
                          f" return c && c.width > {before['canvas']} * 1.3; }})()")  # redessinée plus nette (limite mémoire iOS)
    assert not is_playing(app)
    pinch(app, 0.2)
    settle(app)
    back = page_metrics(app)
    assert back["pw"] == pytest.approx(before["pw"], rel=0.02) and back["scrollW"] <= back["sw"] + 1


def test_AFF12_pdf_zoom_is_remembered(app, books):
    import_books(app, books, "long.pdf")
    open_book(app, "long")
    w = page_metrics(app)["pw"]
    pinch(app, 1.5)
    settle(app)
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(app, "long")
    assert page_metrics(app)["pw"] == pytest.approx(1.5 * w, rel=0.02)


def test_AFF12_resize_without_size_change_is_ignored(app, books):
    import_books(app, books, "long.pdf")
    open_book(app, "long")
    set_ratio(app, 0.4)
    app.wait_for_function("document.querySelector('.page canvas')")
    app.wait_for_timeout(500)
    app.evaluate("window.__c = document.querySelector('.page canvas'); window.dispatchEvent(new Event('resize'))")
    app.wait_for_timeout(500)
    assert app.evaluate("window.__c.isConnected"), "les pages ne doivent pas être redessinées pour rien"
