"""DEF-12 : le texte garde une couche graphique stable (pas de zones vides sur iPhone)."""
from helpers import import_books, open_book, install_clock, tap_text

WATCH = """() => { window.__tf = [];
  const c = document.getElementById('content');
  new MutationObserver(() => window.__tf.push(c.style.transform)).observe(c, { attributes: true, attributeFilter: ['style'] }); }"""


def test_DEF12_layer_never_destroyed(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    install_clock(app)
    assert app.evaluate("document.getElementById('content').style.transform").startswith("translate3d")
    app.evaluate(WATCH)
    tap_text(app)                                   # lecture
    app.clock.run_for(2000)
    app.dispatch_event("#scroller", "touchstart")   # le doigt se pose
    app.dispatch_event("#scroller", "touchend")
    app.clock.run_for(1500)                         # reprise
    tap_text(app)                                   # pause
    seen = app.evaluate("window.__tf")
    assert seen, "le défilement doit décaler le texte"
    assert all(t.startswith("translate3d") for t in seen), seen


def test_DEF12_epub_images_decode_async(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    decs = app.evaluate("[...document.querySelectorAll('.epub-body img')].map(i => i.getAttribute('decoding'))")
    assert decs and all(d == "async" for d in decs), decs
