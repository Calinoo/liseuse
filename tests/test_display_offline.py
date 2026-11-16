"""Affichage (AFF-1..5) et hors connexion (OFF-1..3)."""
import json

import pytest

from helpers import import_books, open_book, ratio, set_ratio


def _open_epub(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")


def _settings(app):
    app.locator("#settingsBtn").click()
    assert app.locator("#settings").is_visible()


@pytest.mark.parametrize("theme, bg", [("light", "rgb(250, 248, 243)"), ("sepia", "rgb(244, 236, 216)"),
                                       ("dark", "rgb(18, 18, 18)")])
def test_AFF1_themes(app, books, theme, bg):
    _open_epub(app, books)
    _settings(app)
    app.locator(f"#themeSeg [data-theme={theme}]").click()
    assert app.evaluate("document.documentElement.dataset.theme") == theme
    assert app.evaluate("getComputedStyle(document.getElementById('readerView')).backgroundColor") == bg


def test_AFF1_dark_theme_inverts_pdf_pages(app, books):
    import_books(app, books, "sample.pdf")
    open_book(app, "sample")
    _settings(app)
    app.locator("#themeSeg [data-theme=dark]").click()
    assert "invert" in app.evaluate("getComputedStyle(document.querySelector('.page')).filter")


def test_AFF2_font_size_bounds_and_family(app, books):
    _open_epub(app, books)
    _settings(app)
    for _ in range(25):
        app.locator("#fontUp").click()
    assert app.locator("#fontVal").inner_text() == "34"
    assert app.evaluate("getComputedStyle(document.querySelector('.epub-body')).fontSize") == "34px"
    for _ in range(30):
        app.locator("#fontDown").click()
    assert app.locator("#fontVal").inner_text() == "13"
    app.locator("#fontSeg [data-font=sans]").click()
    assert "Georgia" not in app.evaluate("getComputedStyle(document.querySelector('.epub-body')).fontFamily")


def test_AFF2_text_settings_hidden_for_pdf(app, books):
    import_books(app, books, "sample.pdf")
    open_book(app, "sample")
    _settings(app)
    assert app.locator("#themeSeg").is_visible()
    assert not app.locator("#fontUp").is_visible()


def test_AFF3_font_change_keeps_position(app, books):
    _open_epub(app, books)
    set_ratio(app, 0.5)
    _settings(app)
    for _ in range(6):
        app.locator("#fontUp").click()
    app.wait_for_timeout(100)
    assert ratio(app) == pytest.approx(0.5, abs=0.02)
    app.locator("#fontSeg [data-font=sans]").click()
    app.wait_for_timeout(100)
    assert ratio(app) == pytest.approx(0.5, abs=0.02)


def test_AFF4_display_settings_remembered(app, books):
    _open_epub(app, books)
    _settings(app)
    app.locator("#themeSeg [data-theme=sepia]").click()
    app.locator("#fontUp").click()
    app.locator("#fontSeg [data-font=sans]").click()
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    assert app.evaluate("document.documentElement.dataset.theme") == "sepia"
    open_book(app, "Mon livre de test")
    _settings(app)
    assert app.locator("#fontVal").inner_text() == "20"
    assert "on" in app.locator("#fontSeg [data-font=sans]").get_attribute("class")


@pytest.mark.parametrize("orientation", ["portrait", "paysage"])
def test_AFF5_no_horizontal_overflow(app, books, orientation):
    if orientation == "paysage":
        vp = app.viewport_size
        app.set_viewport_size({"width": vp["height"], "height": vp["width"]})
    no_overflow = "document.documentElement.scrollWidth <= window.innerWidth"
    import_books(app, books, "sample.epub", "sample.pdf")
    assert app.evaluate(no_overflow), "bibliothèque"
    open_book(app, "Mon livre de test")
    _settings(app)
    assert app.evaluate(no_overflow), "lecteur"
    assert app.evaluate("document.getElementById('scroller').scrollWidth "
                        "<= document.getElementById('scroller').clientWidth")
    for sel in ["#playBtn", "#speed", "#settingsBtn", "#backBtn"]:
        box = app.locator(sel).bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= app.viewport_size["width"], sel


# ---------------- Hors connexion ----------------
def test_OFF1_app_starts_without_network(app, ctx, books):
    if ctx.engine == "webkit":
        pytest.skip("Playwright WebKit ne prend pas en charge les service workers")
    app.wait_for_function("navigator.serviceWorker.controller || navigator.serviceWorker.ready")
    app.reload()
    app.wait_for_function("navigator.serviceWorker.controller")
    import_books(app, books, "sample.pdf", "sample.epub")
    ctx.set_offline(True)
    try:
        app.reload()
        app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
        open_book(app, "sample")
        app.wait_for_function("document.querySelector('.page canvas')")
        open_book_epub = app.locator("#backBtn")
        open_book_epub.click()
        open_book(app, "Mon livre de test")
        assert app.locator(".chapter").count() == 3
    finally:
        ctx.set_offline(False)


def test_OFF1_every_cached_asset_exists(app, base_url):
    assets = app.evaluate("""async () => {
        const src = await (await fetch('sw.js')).text();
        return JSON.parse(src.match(/ASSETS = (\\[[\\s\\S]*?\\]);/)[1].replace(/'/g, '"').replace(/,\\s*\\]/, ']'));
    }""")
    for a in ["index.html", "core.js", "app.js", "style.css", "vendor/pdf.worker.min.js"]:
        assert a in assets, f"{a} absent du cache hors ligne"
    for a in assets:
        assert app.request.get(f"{base_url}/{a}").ok, a


def test_OFF2_books_never_leave_the_device(app, books, base_url):
    requests = []
    app.on("request", lambda r: requests.append(r))
    import_books(app, books, "sample.pdf", "sample.epub")
    open_book(app, "sample")
    app.locator("#backBtn").click()
    open_book(app, "Mon livre de test")
    for r in requests:
        if r.url.startswith("blob:") or r.url.startswith("data:"):
            continue
        assert r.url.startswith(base_url), f"requête externe : {r.url}"
        assert r.method == "GET", f"envoi de données : {r.method} {r.url}"
        assert "/tests/" not in r.url, f"fichier livre envoyé : {r.url}"


def test_OFF3_installable(app, base_url):
    manifest = json.loads(app.request.get(f"{base_url}/manifest.webmanifest").text())
    assert manifest["display"] == "standalone"
    assert manifest["start_url"] == "./"
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert {"192x192", "512x512"} <= sizes
    for icon in manifest["icons"]:
        assert app.request.get(f"{base_url}/{icon['src']}").ok
    assert app.locator("link[rel=apple-touch-icon]").count() == 1
    assert app.locator("meta[name=apple-mobile-web-app-capable]").get_attribute("content") == "yes"


@pytest.mark.parametrize("name, title", [("sample.epub", "Mon livre de test"), ("long.pdf", "long")])
def test_AFF6_rotation_keeps_position(app, books, name, title):
    import_books(app, books, name)
    open_book(app, title)
    set_ratio(app, 0.4)
    app.wait_for_timeout(100)
    vp = app.viewport_size
    for size in ({"width": vp["height"], "height": vp["width"]}, vp):  # paysage puis retour
        app.set_viewport_size(size)
        app.wait_for_timeout(700)
        assert ratio(app) == pytest.approx(0.4, abs=0.01), size


def test_AFF7_immersive_status_bar_and_full_bleed(app, books):
    assert app.locator("meta[name=apple-mobile-web-app-status-bar-style]").get_attribute("content") \
        == "black-translucent"
    assert "viewport-fit=cover" in app.locator("meta[name=viewport]").get_attribute("content")
    _open_epub(app, books)
    box = app.locator("#scroller").bounding_box()
    vp = app.viewport_size
    assert box["y"] == 0 and box["height"] == vp["height"], "le texte doit couvrir tout l'écran"


FS_STUB = """
    window.__fs = [];
    Object.defineProperty(document, 'fullscreenEnabled', { configurable: true, get: () => %s });
    Object.defineProperty(document, 'webkitFullscreenEnabled', { configurable: true, get: () => %s });
    Element.prototype.requestFullscreen = function () { window.__fs.push('enter'); return Promise.resolve(); };
    Element.prototype.webkitRequestFullscreen = Element.prototype.requestFullscreen;
"""


def _page_with(ctx, base_url, script):
    page = ctx.new_page()
    page.add_init_script(script)
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    return page


def test_AFF8_fullscreen_button_when_supported(ctx, base_url, books):
    page = _page_with(ctx, base_url, FS_STUB % ("true", "true"))
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")
    assert page.locator("#fsBtn").is_visible()
    page.locator("#fsBtn").click()
    page.wait_for_function("window.__fs.length === 1")


def test_AFF8_no_fullscreen_button_when_unsupported(ctx, base_url, books):
    page = _page_with(ctx, base_url, FS_STUB % ("false", "false"))
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")
    assert not page.locator("#fsBtn").is_visible()


def test_AFF8_no_fullscreen_button_when_installed(ctx, base_url, books):
    script = FS_STUB % ("true", "true") + """
        const mm = window.matchMedia.bind(window);
        window.matchMedia = q => q.includes('display-mode') ? { matches: true, media: q,
            addEventListener() {}, removeEventListener() {} } : mm(q);
    """
    page = _page_with(ctx, base_url, script)
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")
    assert not page.locator("#fsBtn").is_visible()
