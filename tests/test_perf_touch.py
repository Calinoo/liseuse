"""DEF-11 : le défilement au doigt ne doit jamais attendre le code de l'app."""
from helpers import import_books, open_book

SPY = """
(() => {
  window.__blocking = [];
  const orig = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, opts) {
    if (['touchstart', 'touchmove', 'wheel', 'mousewheel'].includes(type)) {
      const passive = typeof opts === 'object' && opts !== null && opts.passive === true;
      const stack = String(new Error().stack);
      // seulement le code de l'app (les outils de test ajoutent les leurs)
      if (!passive && /\/(app|core)\.js|\/vendor\//.test(stack)) window.__blocking.push(type + ' sur ' + (this.id || this.nodeName || String(this)) + ' @ ' + String(new Error().stack).split('\\n').slice(1, 3).join(' | '));
    }
    return orig.call(this, type, fn, opts);
  };
})();
"""


def test_DEF11_no_blocking_touch_listener(ctx, base_url, books):
    page = ctx.new_page()
    page.add_init_script(SPY)
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    import_books(page, books, "sample.epub", "long.pdf")
    open_book(page, "long")
    assert page.evaluate("window.__blocking") == []


def test_DEF11_scroller_keeps_native_touch_action(app):
    for sel in ("html", "body", "#scroller", "#content"):
        ta = app.evaluate(f"getComputedStyle(document.querySelector('{sel}')).touchAction")
        assert "pan-" not in ta, f"{sel} : {ta}"


SPY_MOVE = """
(() => {
  window.__moves = 0;
  const orig = EventTarget.prototype.addEventListener, origRm = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (type, fn, o) {
    if (type === 'pointermove' && this.id === 'scroller') window.__moves++;
    return orig.call(this, type, fn, o);
  };
  EventTarget.prototype.removeEventListener = function (type, fn, o) {
    if (type === 'pointermove' && this.id === 'scroller') window.__moves--;
    return origRm.call(this, type, fn, o);
  };
})();
"""


def test_DEF11_pointermove_only_during_press(ctx, base_url, books):
    page = ctx.new_page()
    page.add_init_script(SPY_MOVE)
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    import_books(page, books, "sample.epub")
    open_book(page, "Mon livre de test")
    assert page.evaluate("window.__moves") == 0, "aucun suivi des mouvements hors appui"
    page.dispatch_event("#scroller", "pointerdown", {"clientX": 50, "clientY": 300, "pointerType": "touch", "pointerId": 3})
    assert page.evaluate("window.__moves") == 1
    page.dispatch_event("#scroller", "pointerup", {"clientX": 50, "clientY": 300, "pointerType": "touch", "pointerId": 3})
    assert page.evaluate("window.__moves") == 0
