"""Navigation rapide : NAV-1 à NAV-4."""
import pytest

from helpers import import_books, open_book, ratio, set_ratio, is_playing, install_clock, tap_text


def _open(app, books, name, title):
    import_books(app, books, name)
    open_book(app, title)


def seek(page, permille):
    page.locator("#seek").fill(str(permille))


def test_NAV1_seek_bar_jumps_anywhere(app, books):
    _open(app, books, "sample.epub", "Mon livre de test")
    assert app.locator("#seek").is_visible()
    seek(app, 500)
    assert ratio(app) == pytest.approx(0.5, abs=0.01)
    app.wait_for_function("document.getElementById('pct').textContent === '50 %'")


def test_NAV2_seek_pauses_and_labels_chapter(app, books):
    _open(app, books, "sample.epub", "Mon livre de test")
    install_clock(app)
    tap_text(app)
    app.clock.run_for(500)
    assert is_playing(app)
    app.evaluate("document.getElementById('seek').dispatchEvent(new Event('pointerdown'))")
    seek(app, 995)
    assert not is_playing(app)
    label = app.locator("#seekLabel")
    assert label.is_visible() and label.inner_text() == "Chapitre 3"
    seek(app, 0)
    assert label.inner_text() == "Chapitre 1"


def test_NAV2_pdf_label_shows_page(app, books):
    _open(app, books, "long.pdf", "long")
    seek(app, 1000)
    assert app.locator("#seekLabel").inner_text() == "Page 30 / 30"
    seek(app, 0)
    assert app.locator("#seekLabel").inner_text() == "Page 1 / 30"


def test_NAV3_seek_bar_follows_reading(app, books):
    _open(app, books, "sample.epub", "Mon livre de test")
    set_ratio(app, 0.3)
    app.wait_for_function("Math.abs(document.getElementById('seek').value - 300) <= 10")


def test_NAV4_jump_is_saved(app, books):
    _open(app, books, "long.pdf", "long")
    seek(app, 700)
    app.wait_for_function("Math.abs(window.LiseuseApp.lastSavedProgress - 0.7) < 0.01", timeout=3500)
