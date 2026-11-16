"""Bibliothèque : exigences BIB-1 à BIB-8."""
import os

from helpers import wait_dialog, import_books, library_titles, open_book, back_to_library, stored_books


def test_BIB1_empty_library_shows_help(app):
    assert app.locator(".book").count() == 0
    assert app.locator("#empty").is_visible()
    assert "Ajouter un livre" in app.locator("#empty").inner_text()


def test_BIB2_picker_accepts_pdf_epub_multiple(app):
    inp = app.locator("#fileInput")
    accept = inp.get_attribute("accept")
    assert ".pdf" in accept and ".epub" in accept
    assert inp.get_attribute("multiple") is not None
    with app.expect_file_chooser() as fc:
        app.locator("#addBtn").click()
    assert fc.value.is_multiple()


def test_BIB2_import_several_at_once(app, books):
    import_books(app, books, "sample.pdf", "sample.epub")
    assert app.locator(".book").count() == 2
    assert not app.locator("#empty").is_visible()


def test_BIB3_rejects_other_files_but_imports_the_rest(app, books):
    import_books(app, books, "notes.txt", "sample.pdf", expect_count=1)
    assert any("notes.txt" in d for d in app.dialogs)
    assert library_titles(app) == ["sample"]


def test_BIB3_BIB4_uppercase_extension_and_no_title(app, books):
    import_books(app, books, "NoTitle.EPUB")
    assert library_titles(app) == ["NoTitle"]
    assert app.locator(".book .cover").inner_text() == "EPUB"


def test_BIB4_epub_title_from_metadata(app, books):
    import_books(app, books, "sample.epub")
    assert library_titles(app) == ["Mon livre de test"]


def test_BIB5_most_recently_opened_first(app, books):
    import_books(app, books, "sample.pdf")
    import_books(app, books, "sample.epub")
    assert library_titles(app) == ["Mon livre de test", "sample"]
    open_book(app, "sample")
    back_to_library(app)
    assert library_titles(app) == ["sample", "Mon livre de test"]


def test_BIB6_card_shows_type_progress_and_size(app, books):
    import_books(app, books, "sample.pdf")
    card = app.locator(".book")
    assert card.locator(".cover").inner_text() == "PDF"
    size_ko = round(os.path.getsize(books("sample.pdf")) / 1000)
    assert card.locator(".meta").inner_text() == f"0 % lu · {size_ko} Ko"
    assert card.locator(".progress span").get_attribute("style") == "width:0%"


def test_BIB7_delete_needs_confirmation(app, books):
    import_books(app, books, "sample.pdf")
    app.dialog_answer = False
    app.locator(".book .del").click()
    wait_dialog(app, "Retirer")
    assert app.locator(".book").count() == 1
    app.dialog_answer = True
    app.locator(".book .del").click()
    app.wait_for_function("document.querySelectorAll('.book').length === 0")
    assert stored_books(app) == []
    assert app.locator("#empty").is_visible()


def test_BIB8_books_survive_reload(app, books):
    import_books(app, books, "sample.pdf", "sample.epub")
    app.reload()
    app.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    assert sorted(library_titles(app)) == ["Mon livre de test", "sample"]


def test_BIB9_same_file_not_duplicated(app, books):
    import_books(app, books, "sample.pdf")
    app.set_input_files("#fileInput", [books("sample.pdf")])
    wait_dialog(app, "déjà")
    assert app.locator(".book").count() == 1
    h = stored_books(app)[0]["hash"]
    assert len(h) == 64 and all(c in "0123456789abcdef" for c in h)


def test_BIB9_old_books_get_fingerprint_on_open(app, books):
    import_books(app, books, "sample.pdf")
    app.evaluate("""() => new Promise(res => {
        const r = indexedDB.open('liseuse');
        r.onsuccess = () => {
            const st = r.result.transaction('books', 'readwrite').objectStore('books');
            st.getAll().onsuccess = e => { const b = e.target.result[0]; delete b.hash;
                st.put(b).onsuccess = () => { r.result.close(); res(); }; };
        };
    })""")
    assert "hash" not in stored_books(app)[0]
    open_book(app, "sample")
    back_to_library(app)
    assert len(stored_books(app)[0]["hash"]) == 64
