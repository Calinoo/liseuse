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


def test_DEF11_zoom_blocked_by_css(app):
    ta = app.evaluate("getComputedStyle(document.getElementById('scroller')).touchAction")
    assert ta in ("pan-x pan-y", "pan-y pan-x"), ta
