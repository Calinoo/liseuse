"""Défilement automatique : DEF-1 à DEF-8.

Le temps est simulé (page.clock) : les mesures sont exactes et le test est rapide.
"""
import pytest

from helpers import (import_books, open_book, scroll_top, set_ratio, set_scroll, tap_text,
                     is_playing, bars_hidden, install_clock, SCROLL)


@pytest.fixture
def reading(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    install_clock(app)
    return app


def set_speed(page, v):
    page.locator("#speed").fill(str(v))


def test_DEF1_tap_toggles_play_pause(reading):
    tap_text(reading)
    assert is_playing(reading)
    assert reading.locator("#playBtn").inner_text() == "❚❚"
    tap_text(reading)
    assert not is_playing(reading)
    assert reading.locator("#playBtn").inner_text() == "▶"


def test_DEF1_button_toggles_play_pause(reading):
    reading.locator("#playBtn").click()
    assert is_playing(reading)
    reading.locator("#playBtn").click()
    assert not is_playing(reading)


@pytest.mark.parametrize("speed", [5, 30, 120])
def test_DEF2_scrolls_at_set_speed(reading, speed):
    set_speed(reading, speed)
    start = scroll_top(reading)
    tap_text(reading)
    reading.clock.run_for(4000)
    moved = scroll_top(reading) - start
    assert moved == pytest.approx(4 * speed, abs=3)


def test_DEF2_independent_of_frame_rate(reading):
    """Une saccade (onglet ralenti) ne doit ni accélérer ni faire sauter le texte."""
    set_speed(reading, 60)
    tap_text(reading)
    reading.clock.run_for(1000)
    a = scroll_top(reading)
    reading.clock.run_for(1000)
    assert scroll_top(reading) - a == pytest.approx(60, abs=3)


def test_DEF3_speed_bounds_and_steps(reading):
    set_speed(reading, 19)
    reading.locator("#faster").click()
    assert reading.locator("#speedVal").inner_text() == "20"
    reading.locator("#faster").click()
    assert reading.locator("#speedVal").inner_text() == "22"
    set_speed(reading, 60)
    reading.locator("#slower").click()
    assert reading.locator("#speedVal").inner_text() == "55"
    set_speed(reading, 200)
    reading.locator("#faster").click()
    assert reading.locator("#speedVal").inner_text() == "200"
    set_speed(reading, 5)
    reading.locator("#slower").click()
    assert reading.locator("#speedVal").inner_text() == "5"


def test_DEF3_speed_is_remembered(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    app.locator("#speed").fill("77")
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    open_book(app, "Mon livre de test")
    assert app.locator("#speed").input_value() == "77"
    assert app.locator("#speedVal").inner_text() == "77"


def test_DEF4_finger_suspends_then_resumes_from_new_position(reading):
    set_speed(reading, 50)
    tap_text(reading)
    reading.clock.run_for(1000)
    reading.dispatch_event("#scroller", "touchstart")
    set_scroll(reading, 1500)  # l'utilisateur fait glisser
    reading.clock.run_for(1000)
    assert scroll_top(reading) == pytest.approx(1500, abs=1), "le défilement doit être suspendu"
    reading.dispatch_event("#scroller", "touchend")
    reading.clock.run_for(600)
    assert scroll_top(reading) == pytest.approx(1500, abs=1), "pas de reprise avant 0,7 s"
    reading.clock.run_for(1100)
    assert scroll_top(reading) == pytest.approx(1500 + 50, abs=6)
    assert is_playing(reading)


def test_DEF5_stops_at_end(reading):
    set_speed(reading, 200)
    set_ratio(reading, 1)
    set_scroll(reading, scroll_top(reading) - 100)
    tap_text(reading)
    reading.clock.run_for(2000)
    assert not is_playing(reading)
    assert reading.evaluate(f"(s => s.scrollTop + s.clientHeight >= s.scrollHeight - 2)({SCROLL})")


def test_DEF6_bars_hide_while_playing_and_return_on_pause(reading):
    tap_text(reading)
    reading.clock.run_for(1500)
    assert not bars_hidden(reading)
    reading.clock.run_for(800)
    assert bars_hidden(reading)
    tap_text(reading)
    assert not bars_hidden(reading)


def test_DEF7_background_pauses_and_saves(reading):
    tap_text(reading)
    reading.clock.run_for(2000)
    reading.evaluate("""() => {
        Object.defineProperty(document, 'hidden', { configurable: true, get: () => true });
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    assert not is_playing(reading)
    reading.wait_for_function("window.LiseuseApp.lastSavedProgress > 0")


def test_DEF8_wake_lock_requested_and_released(ctx, base_url, books):
    page = ctx.new_page()
    page.add_init_script("""
        window.__wake = [];
        Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
            request: async (t) => { window.__wake.push('request:' + t);
                return { release: async () => window.__wake.push('release') }; } } });
    """)
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")
    tap_text(page)
    page.wait_for_function("window.__wake.length === 1")
    tap_text(page)
    page.wait_for_function("window.__wake.length === 2")
    assert page.evaluate("window.__wake") == ["request:screen", "release"]
