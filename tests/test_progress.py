"""Progression et temps restant : PROG-1 à PROG-7."""
import pytest

from helpers import (import_books, open_book, back_to_library, ratio, set_ratio, pct_text,
                     remaining_text, stored_books, install_clock, tap_text, SCROLL)


def _open(app, books, name="sample.epub", title="Mon livre de test"):
    import_books(app, books, name)
    open_book(app, title)


def test_PROG2_percentage_in_top_bar(app, books):
    _open(app, books)
    assert pct_text(app) == "0 %"
    set_ratio(app, 0.427)
    app.wait_for_function("document.getElementById('pct').textContent === '43 %'")


def test_PROG3_saved_within_3_seconds_of_moving(app, books):
    _open(app, books)
    set_ratio(app, 0.5)
    app.wait_for_function("window.LiseuseApp.lastSavedProgress > 0.49", timeout=3500)
    assert stored_books(app)[0]["progress"] == pytest.approx(0.5, abs=0.01)


def test_PROG3_saved_on_close(app, books):
    _open(app, books)
    set_ratio(app, 0.3)
    back_to_library(app)
    assert stored_books(app)[0]["progress"] == pytest.approx(0.3, abs=0.01)
    assert app.locator(".book .meta").inner_text().startswith("30 % lu")


@pytest.mark.parametrize("name, title", [("sample.epub", "Mon livre de test"), ("long.pdf", "long")])
def test_PROG4_reopen_resumes_position(app, books, name, title):
    _open(app, books, name, title)
    set_ratio(app, 0.62)
    back_to_library(app)
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(app, title)
    assert ratio(app) == pytest.approx(0.62, abs=0.01)


def _expected_remaining(app, speed):
    return app.evaluate(f"""sp => {{ const s = {SCROLL};
        return LiseuseCore.formatRemaining(
            LiseuseCore.remainingSeconds(s.scrollTop, s.scrollHeight, s.clientHeight, sp)); }}""", speed)


def test_PROG5_remaining_time_shown(app, books):
    _open(app, books)
    app.locator("#speed").fill("10")
    text = remaining_text(app)
    assert text == _expected_remaining(app, 10)
    assert text.startswith("~")


def test_PROG6_remaining_time_finished_at_end(app, books):
    _open(app, books)
    set_ratio(app, 1)
    app.wait_for_function("document.getElementById('remaining').textContent === 'Terminé'")


def test_PROG7_remaining_updates_with_position_and_speed(app, books):
    _open(app, books)
    app.locator("#speed").fill("5")
    slow = remaining_text(app)
    app.locator("#speed").fill("200")
    fast = remaining_text(app)
    assert slow != fast and fast == _expected_remaining(app, 200)
    set_ratio(app, 0.5)
    app.wait_for_function(f"document.getElementById('remaining').textContent !== {fast!r}")
    assert remaining_text(app) == _expected_remaining(app, 200)


def test_PROG7_remaining_updates_while_playing(app, books):
    _open(app, books)
    app.locator("#speed").fill("200")
    install_clock(app)
    before = remaining_text(app)
    tap_text(app)
    app.clock.run_for(70_000)
    assert remaining_text(app) != before
