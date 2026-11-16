"""Tests unitaires de core.js (logique pure, sans interface).

Exécutés dans WebKit, le moteur de Safari iOS.
"""
import pytest


# ---------- BIB-3 : détection du type ----------
@pytest.mark.parametrize("name, mime, expected", [
    ("livre.pdf", "", "pdf"),
    ("LIVRE.PDF", "", "pdf"),
    ("roman.epub", "", "epub"),
    ("Roman.EPUB", "", "epub"),
    ("sans-extension", "application/pdf", "pdf"),
    ("sans-extension", "application/epub+zip", "epub"),
    ("notes.txt", "text/plain", None),
    ("archive.epub.zip", "application/zip", None),
])
def test_BIB3_detect_type(core, name, mime, expected):
    assert core("detectType", name, mime) == expected


# ---------- BIB-4 : titre par défaut ----------
@pytest.mark.parametrize("name, expected", [
    ("Mon roman.pdf", "Mon roman"),
    ("a.b.c.epub", "a.b.c"),
    ("sans", "sans"),
])
def test_BIB4_title_from_filename(core, name, expected):
    assert core("titleFromFilename", name) == expected


# ---------- BIB-6 : taille lisible ----------
@pytest.mark.parametrize("n, expected", [
    (200, "1 Ko"), (15_000, "15 Ko"), (999_000, "999 Ko"),
    (1_200_000, "1,2 Mo"), (25_000_000, "25,0 Mo"),
])
def test_BIB6_format_size(core, n, expected):
    assert core("formatSize", n) == expected


# ---------- EPUB-2 : résolution des chemins ----------
@pytest.mark.parametrize("base, href, expected", [
    ("OEBPS/Text/", "../Images/a.png", "OEBPS/Images/a.png"),
    ("OEBPS/Text/", "../Images/ma%20photo.png", "OEBPS/Images/ma photo.png"),
    ("OEBPS/", "Text/ch1.xhtml#x", "OEBPS/Text/ch1.xhtml"),
    ("OEBPS/", "./Text/ch1.xhtml?v=2", "OEBPS/Text/ch1.xhtml"),
    ("OEBPS/Text/", "/racine.png", "racine.png"),
    ("", "content.opf", "content.opf"),
    ("a/b/", "../../../c.png", "c.png"),
    ("OEBPS/", "bad%E0.png", "OEBPS/bad%E0.png"),
])
def test_EPUB2_resolve_path(core, base, href, expected):
    assert core("resolvePath", base, href) == expected


@pytest.mark.parametrize("path, expected", [
    ("OEBPS/content.opf", "OEBPS/"), ("content.opf", ""), ("a/b/c.xhtml", "a/b/"),
])
def test_EPUB2_dir_of(core, path, expected):
    assert core("dirOf", path) == expected


@pytest.mark.parametrize("path, expected", [
    ("a.JPG", "image/jpeg"), ("a.jpeg", "image/jpeg"), ("a.png", "image/png"),
    ("a.gif", "image/gif"), ("a.svg", "image/svg+xml"), ("a.webp", "image/webp"),
    ("a.bin", "application/octet-stream"),
])
def test_EPUB2_mime(core, path, expected):
    assert core("mimeOf", path) == expected


# ---------- EPUB-4 / EPUB-5 : cibles des liens ----------
INDEX = {"OEBPS/Text/ch1.xhtml": 0, "OEBPS/Text/ch3.xhtml": 2}


@pytest.mark.parametrize("href, expected", [
    ("ch3.xhtml#fin", {"type": "internal", "id": "c2-fin"}),
    ("ch3.xhtml", {"type": "internal", "id": "c2"}),
    ("#note1", {"type": "internal", "id": "c0-note1"}),
    ("https://example.com/", {"type": "external", "url": "https://example.com/"}),
    ("HTTP://example.com/", {"type": "external", "url": "HTTP://example.com/"}),
    ("javascript:alert(1)", None),
    ("mailto:a@b.c", None),
    ("inconnu.xhtml#x", None),
    ("", None),
])
def test_EPUB4_link_target(core, href, expected):
    assert core("linkTarget", href, {"chapter": 0, "dir": "OEBPS/Text/", "index": INDEX}) == expected


# ---------- DEF-3 : vitesse ----------
@pytest.mark.parametrize("v, expected", [(0, 5), (4.6, 5), (30.4, 30), (250, 200), (-10, 5), ("abc", 30)])
def test_DEF3_clamp_speed(core, v, expected):
    assert core("clampSpeed", v) == expected


@pytest.mark.parametrize("v, expected", [(5, 1), (19, 1), (20, 2), (59, 2), (60, 5), (200, 5)])
def test_DEF3_speed_step(core, v, expected):
    assert core("speedStep", v) == expected


# ---------- AFF-2 : taille du texte ----------
@pytest.mark.parametrize("v, expected", [(12, 13), (13, 13), (19, 19), (34, 34), (40, 34)])
def test_AFF2_clamp_font_size(core, v, expected):
    assert core("clampFontSize", v) == expected


# ---------- PROG-1 : progression ----------
@pytest.mark.parametrize("top, height, client, expected", [
    (0, 2000, 800, 0), (600, 2000, 800, 0.5), (1200, 2000, 800, 1),
    (1500, 2000, 800, 1),   # dépassement (rebond iOS)
    (-40, 2000, 800, 0),    # rebond iOS en haut
    (0, 500, 800, 0),       # contenu plus court que l'écran
])
def test_PROG1_progress_ratio(core, top, height, client, expected):
    assert core("progressRatio", top, height, client) == pytest.approx(expected)


# ---------- PROG-5 : temps restant ----------
@pytest.mark.parametrize("top, height, client, speed, expected", [
    (0, 3800, 800, 30, 100),
    (1500, 3800, 800, 30, 50),
    (3000, 3800, 800, 30, 0),
    (3100, 3800, 800, 30, 0),
    (0, 500, 800, 30, 0),
])
def test_PROG5_remaining_seconds(core, top, height, client, speed, expected):
    assert core("remainingSeconds", top, height, client, speed) == pytest.approx(expected)


# ---------- PROG-6 : format du temps restant ----------
@pytest.mark.parametrize("sec, expected", [
    (0, "Terminé"),
    (0.4, "Terminé"),
    (1, "< 1 min"),
    (59, "< 1 min"),
    (60, "~1 min"),
    (89, "~1 min"),
    (90, "~2 min"),
    (25 * 60, "~25 min"),
    (59 * 60 + 29, "~59 min"),
    (59 * 60 + 30, "~1 h 00"),
    (3600, "~1 h 00"),
    (3600 + 5 * 60, "~1 h 05"),
    (2 * 3600 + 47 * 60, "~2 h 47"),
])
def test_PROG6_format_remaining(core, sec, expected):
    assert core("formatRemaining", sec) == expected


# ---------- NAV-2 : retrouver la section / page à une position ----------
@pytest.mark.parametrize("offsets, y, expected", [
    ([0, 100, 250], 0, 0),
    ([0, 100, 250], 99, 0),
    ([0, 100, 250], 100, 1),
    ([0, 100, 250], 9999, 2),
    ([50, 100], 10, 0),      # avant la première section
    ([], 10, -1),            # livre vide
    ([0], 0, 0),
])
def test_NAV2_locate(core, offsets, y, expected):
    assert core("locate", offsets, y) == expected


@pytest.mark.parametrize("i, n, expected", [(0, 30, "Page 1 / 30"), (29, 30, "Page 30 / 30")])
def test_NAV2_page_label(core, i, n, expected):
    assert core("pageLabel", i, n) == expected
