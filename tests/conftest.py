"""Infrastructure de test commune.

- Un petit serveur HTTP sert le dossier de l'app (comme en production).
- Les tests de bout en bout tournent sur 3 cibles :
  WebKit (moteur de Safari) en iPhone, WebKit en iPad, Chromium en iPhone.
- Chaque test part d'un contexte de navigateur vierge (IndexedDB et localStorage vides).
"""
import functools
import http.server
import os
import socketserver
import threading

import pytest
from playwright.sync_api import sync_playwright

from fixtures.make_books import build

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGETS = {
    "webkit-iphone": ("webkit", "iPhone 13"),
    "webkit-ipad": ("webkit", "iPad (gen 7)"),
    "chromium-iphone": ("chromium", "iPhone 13"),
}


# Socle stratégique : les parcours qui ne doivent JAMAIS casser. Toujours exécutés.
STRATEGIC = (
    "test_BIB2_import_several_at_once", "test_BIB8_books_survive_reload",
    "test_PDF1_pages_full_width", "test_PDF2_only_nearby_pages", "test_EPUB1_all_chapters",
    "test_EPUB3_book_cannot_run_code", "test_DEF1_tap_toggles", "test_DEF2_scrolls_at_set_speed",
    "test_DEF9_smooth_subpixel", "test_PROG4_reopen_resumes", "test_OFF1_", "test_OFF2_",
    "test_NAV1_", "test_SRCH5_go_to_result_epub", "test_AFF6_rotation",
)


def pytest_configure(config):
    config.addinivalue_line("markers", "strategic: parcours critique, exécuté à chaque vérification")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if item.originalname.startswith(STRATEGIC):
            item.add_marker(pytest.mark.strategic)


def pytest_addoption(parser):
    parser.addoption("--target", action="append", choices=list(TARGETS),
                     help="Cible(s) à tester (par défaut : toutes)")


def pytest_generate_tests(metafunc):
    if "target" in metafunc.fixturenames:
        chosen = metafunc.config.getoption("target") or list(TARGETS)
        metafunc.parametrize("target", chosen, scope="session")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


@pytest.fixture(scope="session")
def base_url():
    handler = functools.partial(_Quiet, directory=APP_DIR)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


@pytest.fixture(scope="session")
def books():
    d = build()
    return lambda name: os.path.join(d, name)


@pytest.fixture(scope="session")
def pw():
    with sync_playwright() as p:
        yield p


_browsers = {}


@pytest.fixture(scope="session")
def browser_for(pw):
    def get(name):
        if name not in _browsers:
            _browsers[name] = getattr(pw, name).launch()
        return _browsers[name]
    yield get
    for b in _browsers.values():
        b.close()


@pytest.fixture
def ctx(target, pw, browser_for):
    engine, device = TARGETS[target]
    context = browser_for(engine).new_context(**pw.devices[device])
    context.engine = engine
    yield context
    context.close()


@pytest.fixture
def app(ctx, base_url):
    """Page de l'app, chargée, avec bibliothèque vide.

    `app.dialogs` enregistre les messages alert/confirm. Par défaut on accepte ;
    mettre `app.dialog_answer = False` pour refuser un confirm.
    """
    page = ctx.new_page()
    page.dialogs = []
    page.dialog_answer = True
    page.js_errors = []
    page.on("pageerror", lambda e: page.js_errors.append(str(e)))

    def on_dialog(d):
        page.dialogs.append(d.message)
        d.accept() if page.dialog_answer else d.dismiss()

    page.on("dialog", on_dialog)
    # Horloge simulée installée AVANT le chargement (le temps s'écoule normalement tant
    # qu'un test ne le pilote pas) : l'installer après coup crée, sous forte charge, une
    # course où certains minuteurs de l'app restent sur l'horloge réelle.
    page.clock.install()
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseApp && window.LiseuseApp.ready")
    yield page
    assert page.js_errors == [], f"Erreurs JavaScript : {page.js_errors}"


@pytest.fixture(scope="session")
def core_page(pw, browser_for, base_url):
    """Page WebKit pour les tests unitaires de core.js (logique pure)."""
    page = browser_for("webkit").new_page()
    page.goto(base_url + "/index.html")
    page.wait_for_function("window.LiseuseCore")
    yield page
    page.close()


@pytest.fixture
def core(core_page):
    """Appelle une fonction de LiseuseCore : core('formatSize', 1500)."""
    def call(fn, *args):
        return core_page.evaluate("([fn, args]) => LiseuseCore[fn](...args)", [fn, list(args)])
    return call
