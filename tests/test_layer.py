"""DEF-12 : pas de couche graphique au repos ; images décodées en arrière-plan."""
from helpers import import_books, open_book, install_clock, tap_text

def test_DEF12_no_layer_at_rest(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    install_clock(app)
    tf = "document.getElementById('content').style.transform"
    assert app.evaluate(tf) == "", "au repos : aucune transformation"
    tap_text(app)                                   # lecture
    app.clock.run_for(2000)
    app.dispatch_event("#scroller", "touchstart")   # le doigt se pose : défilement natif
    assert app.evaluate(tf) == ""
    app.dispatch_event("#scroller", "touchend")
    tap_text(app)                                   # pause
    assert app.evaluate(tf) == ""


def test_DEF12_epub_images_decode_async(app, books):
    import_books(app, books, "sample.epub")
    open_book(app, "Mon livre de test")
    decs = app.evaluate("[...document.querySelectorAll('.epub-body img')].map(i => i.getAttribute('decoding'))")
    assert decs and all(d == "async" for d in decs), decs
