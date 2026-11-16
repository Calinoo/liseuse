"""Recherche dans le livre : SRCH-1 à SRCH-7."""
import pytest

from helpers import import_books, open_book, is_playing, install_clock, tap_text, SCROLL


def _open(app, books, name="sample.epub", title="Mon livre de test"):
    import_books(app, books, name)
    open_book(app, title)


def search(page, query):
    if not page.locator("#searchPanel").is_visible():
        page.locator("#searchBtn").click()
    page.locator("#searchInput").fill(query)
    page.wait_for_function("document.getElementById('searchStatus').dataset.query === %r" % query)


def status(page):
    return page.locator("#searchStatus").inner_text()


def assert_upper_third_or_end(page, hit):
    """SRCH-5 : passage au tiers supérieur, sauf si la fin du livre empêche de remonter plus."""
    h = page.viewport_size["height"]
    y = hit.bounding_box()["y"]
    at_end = page.evaluate(f"(s => s.scrollTop + s.clientHeight >= s.scrollHeight - 2)({SCROLL})")
    assert 0.2 * h <= y <= 0.45 * h or (at_end and 0 <= y <= h * 0.8), (y, h, at_end)


def test_SRCH1_magnifier_opens_ready_and_pauses(app, books):
    _open(app, books)
    install_clock(app)
    tap_text(app)
    app.clock.run_for(300)
    app.locator("#searchBtn").click()
    assert not is_playing(app)
    assert app.locator("#searchPanel").is_visible()
    assert app.evaluate("document.activeElement.id") == "searchInput"


def test_SRCH2_accents_case_apostrophes_and_formatting(app, books):
    _open(app, books)
    search(app, "baleine elegante")
    assert status(app) == "1 résultat"
    item = app.locator("#searchResults li").first
    assert item.locator("mark").inner_text() == "baleine Élégante"
    search(app, "l'ete  dernier")
    assert status(app) == "1 résultat"


def test_SRCH2_needs_two_characters(app, books):
    _open(app, books)
    search(app, "b")
    assert status(app) == "Tapez au moins 2 caractères"
    assert app.locator("#searchResults li").count() == 0


def test_SRCH3_count_snippet_and_chapter(app, books):
    _open(app, books)
    search(app, "chapitre 2, paragraphe 1")
    assert status(app) == "11 résultats"   # paragraphes 1 et 10 à 19
    first = app.locator("#searchResults li").first
    assert first.locator(".loc").inner_text() == "Chapitre 2"
    assert first.locator("mark").inner_text() == "Chapitre 2, paragraphe 1"
    assert "Il était une fois" in first.locator(".snip").inner_text()
    search(app, "zzzz")
    assert status(app) == "Aucun résultat"


def test_SRCH4_capped_at_200(app, books):
    _open(app, books)
    search(app, "il")   # « Il était » et « tranquillement » : plus de 300 occurrences
    assert status(app) == "200+ résultats"
    assert app.locator("#searchResults li").count() == 200


def test_SRCH5_go_to_result_epub(app, books):
    _open(app, books)
    search(app, "baleine elegante")
    app.locator("#searchResults li").first.click()
    assert not app.locator("#searchPanel").is_visible()
    assert not is_playing(app)
    hit = app.locator(".search-hit").first
    assert hit.is_visible()
    assert_upper_third_or_end(app, hit)
    box, para = hit.bounding_box(), app.locator("#c2-special").bounding_box()
    assert para["y"] - 2 <= box["y"] <= para["y"] + para["height"]
    app.wait_for_function("Math.abs(window.LiseuseApp.lastSavedProgress - "
                          f"{SCROLL}.scrollTop / ({SCROLL}.scrollHeight - {SCROLL}.clientHeight)) < 0.01")


def test_SRCH5_go_to_result_pdf_page(app, books):
    _open(app, books, "long.pdf", "long")
    search(app, "ligne 3 de la page 17")
    assert status(app) == "1 résultat"
    assert app.locator("#searchResults li .loc").inner_text() == "Page 17 / 30"
    app.locator("#searchResults li").first.click()
    hit = app.locator('.page[data-i="16"] .search-hit')
    assert hit.count() == 1 and hit.is_visible()
    assert_upper_third_or_end(app, hit)
    # le surlignage est sur la 3e ligne de la page (pas en haut ni en bas)
    page_box, hit_box = app.locator('.page[data-i="16"]').bounding_box(), hit.bounding_box()
    rel = (hit_box["y"] - page_box["y"]) / page_box["height"]
    assert 0.05 < rel < 0.25, rel


def test_SRCH6_scanned_pdf(app, books):
    _open(app, books, "scan.pdf", "scan")
    search(app, "texte")
    assert status(app) == "Ce PDF ne contient pas de texte cherchable"


def test_SRCH7_close_and_reopen_keeps_results(app, books):
    _open(app, books)
    search(app, "baleine")
    app.locator("#searchClose").click()
    assert not app.locator("#searchPanel").is_visible()
    app.locator("#searchBtn").click()
    assert app.locator("#searchInput").input_value() == "baleine"
    assert status(app) == "1 résultat"
    app.keyboard.press("Escape")
    assert not app.locator("#searchPanel").is_visible()


def test_SRCH7_new_book_resets_search(app, books):
    _open(app, books)
    search(app, "baleine")
    app.locator("#searchClose").click()
    app.locator("#backBtn").click()
    import_books(app, books, "sample.pdf")
    open_book(app, "sample")
    app.locator("#searchBtn").click()
    assert app.locator("#searchInput").input_value() == ""
