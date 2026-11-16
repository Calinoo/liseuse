"""Lecture PDF (PDF-1..4) et EPUB (EPUB-1..6)."""
import pytest

from helpers import wait_dialog, import_books, open_book, ratio, set_ratio, set_scroll, SCROLL


# ---------------- PDF ----------------
def test_PDF1_pages_full_width_true_proportions(app, books):
    import_books(app, books, "sample.pdf")
    open_book(app, "sample")
    pages = app.locator(".page")
    assert pages.count() == 5
    app.wait_for_function("document.querySelector('.page canvas')")
    box = pages.first.bounding_box()
    vw = app.viewport_size["width"]
    assert box["width"] == pytest.approx(min(vw, 1000), abs=1)
    assert box["height"] / box["width"] == pytest.approx(842 / 595, rel=0.01)


def test_PDF2_only_nearby_pages_are_drawn(app, books):
    import_books(app, books, "long.pdf")
    open_book(app, "long")
    app.wait_for_function("document.querySelector('.page[data-i=\"0\"] canvas')")
    drawn = app.locator(".page canvas").count()
    assert 0 < drawn < 15, f"{drawn} pages dessinées sur 30"
    set_ratio(app, 1)
    app.wait_for_function("document.querySelector('.page[data-i=\"29\"] canvas')")
    app.wait_for_function("!document.querySelector('.page[data-i=\"0\"] canvas')")
    assert app.locator(".page canvas").count() < 15


def test_PDF3_corrupt_pdf_shows_error_and_returns(app, books):
    import_books(app, books, "corrupt.pdf")
    app.locator(".book .title").click()
    wait_dialog(app, "Impossible d'ouvrir")
    app.wait_for_selector("#library:not(.hidden)")


def test_PDF4_rotation_keeps_position(app, books):
    import_books(app, books, "long.pdf")
    open_book(app, "long")
    set_ratio(app, 0.4)
    vp = app.viewport_size
    app.set_viewport_size({"width": vp["height"], "height": vp["width"]})
    app.wait_for_timeout(600)
    assert ratio(app) == pytest.approx(0.4, abs=0.01)
    app.wait_for_function("[...document.querySelectorAll('.page')].some(p => p.querySelector('canvas'))")


# ---------------- EPUB ----------------
def _open_epub(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")


def test_EPUB1_all_chapters_in_spine_order(app, books):
    _open_epub(app, books)
    heads = app.locator(".chapter h1").all_inner_texts()
    assert heads == ["Chapitre 1", "Chapitre 2", "Chapitre 3"]
    assert app.locator("#c2-fin").inner_text() == "Fin du livre."


def test_EPUB2_images_with_relative_and_encoded_paths(app, books):
    _open_epub(app, books)
    app.wait_for_function("document.querySelector('#c0-photo').naturalWidth === 40")
    href = app.evaluate("document.querySelector('#c1-svgimg')"
                        ".getAttributeNS('http://www.w3.org/1999/xlink', 'href')")
    assert href.startswith("blob:")


def test_EPUB3_book_cannot_run_code_or_restyle(app, books):
    _open_epub(app, books)
    assert app.evaluate("window.__pwned") is None
    assert app.locator("#content script, #content style, #content link").count() == 0
    trap = app.locator("#c0-piege")
    assert trap.get_attribute("onclick") is None and trap.get_attribute("style") is None
    trap.click()
    assert app.evaluate("window.__pwned") is None
    assert app.locator(".epub-body").is_visible()


def test_EPUB4_internal_link_jumps_and_pauses(app, books):
    _open_epub(app, books)
    app.locator("#playBtn").click()
    app.locator("#c0-lien-fin").click()
    assert app.locator("#playBtn").get_attribute("aria-label") == "Lecture"
    top = app.evaluate(f"document.getElementById('c2-fin').getBoundingClientRect().top "
                       f"- {SCROLL}.getBoundingClientRect().top")
    assert 0 <= top <= app.viewport_size["height"]


def test_EPUB4_same_chapter_anchor(app, books):
    _open_epub(app, books)
    app.locator("#c0-lien-note").click()
    top = app.evaluate("document.getElementById('c0-note1').getBoundingClientRect().top")
    assert 0 <= top <= app.viewport_size["height"]


def test_EPUB5_external_link_asks_first(app, books, ctx):
    _open_epub(app, books)
    app.dialog_answer = False
    pages_before = len(ctx.pages)
    app.locator("#c0-lien-ext").click()
    app.wait_for_timeout(300)
    assert any("example.com" in d for d in app.dialogs)
    assert len(ctx.pages) == pages_before


def test_EPUB6_invalid_epub_clear_error(app, books):
    import_books(app, books, "broken.epub")
    app.locator(".book .title").click()
    wait_dialog(app, "container.xml")
    app.wait_for_selector("#library:not(.hidden)")
