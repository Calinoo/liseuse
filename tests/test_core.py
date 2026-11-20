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


# ---------- SRCH-2 : recherche insensible aux accents / casse / apostrophes ----------
def search(core_page, text, query, maxn=200):
    return core_page.evaluate("([t, q, m]) => LiseuseCore.searchFolded(LiseuseCore.foldText(t), q, m)",
                              [text, query, maxn])


@pytest.mark.parametrize("text, query, expected", [
    ("Une baleine Élégante", "elegante", [[12, 20]]),
    ("L’été dernier", "l'ete", [[0, 5]]),
    ("L'été", "L’ÉTÉ", [[0, 5]]),
    ("deux   espaces", "deux espaces", [[0, 14]]),
    ("ligne\ncoupée", "ligne coupee", [[0, 12]]),
    ("aaa", "aa", [[0, 2]]),                 # pas de chevauchement
    ("Œuvre", "œuvre", [[0, 5]]),
    ("rien ici", "zz", []),
    ("court", "c", []),                     # moins de 2 caractères
    ("court", "  ", []),
    ("a b a b", " a b ", [[0, 3], [4, 7]]),  # espaces autour ignorés
])
def test_SRCH2_search(core_page, text, query, expected):
    got = [[m["start"], m["end"]] for m in search(core_page, text, query)]
    assert got == expected


def test_SRCH2_matches_map_back_to_original_text(core_page):
    text = "Ça été  l’Été"
    for m in search(core_page, text, "ete"):
        assert text[m["start"]:m["end"]].lower() in ("été",)


def test_SRCH4_max_results(core_page):
    assert len(search(core_page, "ab " * 500, "ab", 201)) == 201


SNIP_TEXT = "aaaaa bbbbb ccccc MATCHEDddddd eeeee fffff"


@pytest.mark.parametrize("start, end, expected", [
    (18, 25, {"before": "…bbbbb ccccc ", "match": "MATCHED", "after": "ddddd eeeee…"}),
    (0, 5, {"before": "", "match": "aaaaa", "after": " bbbbb ccccc…"}),
    (37, 42, {"before": "…ddddd eeeee ", "match": "fffff", "after": ""}),
])
def test_SRCH3_snippet(core, start, end, expected):
    assert core("snippet", SNIP_TEXT, start, end, 12) == expected


def test_SRCH3_snippet_collapses_whitespace(core):
    assert core("snippet", "un\n\n  deux trois", 11, 16, 40) == {"before": "un deux ", "match": "trois", "after": ""}


# ---------- AFF-9 : contraste (formule WCAG 2) ----------
@pytest.mark.parametrize("a, b, expected", [
    ("#000000", "#ffffff", 21.0),
    ("#ffffff", "#ffffff", 1.0),
    ("rgb(0, 0, 0)", "rgb(255, 255, 255)", 21.0),
    ("#777777", "#ffffff", 4.48),
])
def test_AFF9_contrast_ratio(core, a, b, expected):
    assert core("contrastRatio", a, b) == pytest.approx(expected, abs=0.01)


@pytest.mark.parametrize("c, expected", [("#e8a54b", [232, 165, 75]), ("rgb(1, 2, 3)", [1, 2, 3]),
                                         ("rgba(10, 20, 30, 0.5)", [10, 20, 30])])
def test_AFF9_parse_color(core, c, expected):
    assert core("parseColor", c) == expected


# ---------- AFF-10 : thème effectif ----------
@pytest.mark.parametrize("s, dark, expected", [
    ({"theme": "sepia", "autoTheme": False, "dayTheme": "light", "nightTheme": "night"}, True, "sepia"),
    ({"theme": "sepia", "autoTheme": True, "dayTheme": "light", "nightTheme": "night"}, True, "night"),
    ({"theme": "sepia", "autoTheme": True, "dayTheme": "green", "nightTheme": "amber"}, False, "green"),
    ({"theme": "sepia", "autoTheme": True}, True, "night"),     # valeurs par défaut
    ({"theme": "sepia", "autoTheme": True}, False, "light"),
    ({"theme": "inconnu"}, False, "light"),                     # thème invalide -> Clair
])
def test_AFF10_effective_theme(core, s, dark, expected):
    assert core("effectiveTheme", s, dark) == expected


# ---------- TTS-2 : découpage en phrases ----------
def sentences(core, text, maxlen=250, breaks=None):
    return [text[a:b] for a, b in core("splitSentences", text, maxlen, breaks or [])]


@pytest.mark.parametrize("text, expected", [
    ("Bonjour. Ça va ? Oui !", ["Bonjour.", "Ça va ?", "Oui !"]),
    ("Il hésita… Puis partit.", ["Il hésita…", "Puis partit."]),
    ("Il hésita... Puis partit.", ["Il hésita...", "Puis partit."]),
    ("« Viens ! » dit-il. Elle vint.", ["« Viens ! » dit-il.", "Elle vint."]),
    ("Il cria : « Non ! » Puis rien.", ["Il cria : « Non ! »", "Puis rien."]),
    ("M. Dupont et Mme Durand arrivent. Fin.", ["M. Dupont et Mme Durand arrivent.", "Fin."]),
    ("Le Dr. Watson, etc. Ensuite.", ["Le Dr. Watson, etc. Ensuite."]),
    ("J. K. Rowling écrit. Bien.", ["J. K. Rowling écrit.", "Bien."]),
    ("Version 2.5 sortie. Ok.", ["Version 2.5 sortie.", "Ok."]),
    ("  espaces   autour.  ", ["espaces   autour."]),
    ("sans ponctuation finale", ["sans ponctuation finale"]),
    ("", []),
    ("   ", []),
])
def test_TTS2_split_sentences(core, text, expected):
    assert sentences(core, text) == expected


def test_TTS2_block_breaks_are_hard_boundaries(core):
    text = "Chapitre 1 Il était une fois. Suite"
    # « Il » commence un nouveau bloc (index 11), « Suite » aussi (index 30)
    assert sentences(core, text, breaks=[11, 30]) == ["Chapitre 1", "Il était une fois.", "Suite"]


def test_TTS2_long_sentence_split_at_punctuation(core):
    text = ("Premier membre de phrase assez long, " * 4 + "deuxième partie qui continue encore ; "
            * 4 + "et une fin.")
    parts = sentences(core, text, 120)
    assert all(len(p) <= 120 for p in parts)
    assert " ".join(parts).replace("  ", " ") == text.strip()
    assert all(p.endswith((",", ";", ".")) for p in parts[:-1])


def test_TTS2_long_sentence_without_punctuation_split_at_space(core):
    text = " ".join(["mot"] * 100)  # 399 caractères, aucune ponctuation
    parts = sentences(core, text, 100)
    assert all(len(p) <= 100 for p in parts)
    assert all(not p.startswith(" ") and not p.endswith(" ") for p in parts)
    assert " ".join(parts) == text


def test_TTS2_unbreakable_word_hard_split(core):
    parts = sentences(core, "x" * 260, 100)
    assert [len(p) for p in parts] == [100, 100, 60]


# ---------- TTS-3 : choix de la voix ----------
VOICES = [
    {"name": "Thomas", "lang": "fr-FR", "localService": True, "default": True},
    {"name": "Amélie (Améliorée)", "lang": "fr-CA", "localService": True},
    {"name": "Audrey (Premium)", "lang": "fr-FR", "localService": True},
    {"name": "Samantha", "lang": "en-US", "localService": True},
    {"name": "Daniel (Enhanced)", "lang": "en-GB", "localService": True},
]


@pytest.mark.parametrize("voices, lang, expected", [
    (VOICES, "fr", "Audrey (Premium)"),
    (VOICES, "fr-FR", "Audrey (Premium)"),
    (VOICES, "fr-CA", "Amélie (Améliorée)"),
    (VOICES[:2], "fr", "Thomas"),            # sans Premium : variante de France d'abord
    (VOICES, "en", "Samantha"),             # région (US) avant qualité
    (VOICES, "en-GB", "Daniel (Enhanced)"),
    (VOICES, "de", "Thomas"),                # langue absente : voix par défaut
    ([], "fr", None),
])
def test_TTS3_pick_voice(core, voices, lang, expected):
    assert core("pickVoice", voices, lang) == expected


# ---------- TTS-6 : vitesse de la voix ----------
@pytest.mark.parametrize("v, expected", [(1, 1), (0.3, 0.5), (2.4, 2), (1.04, 1), (1.26, 1.3), ("x", 1)])
def test_TTS6_clamp_rate(core, v, expected):
    assert core("clampTtsRate", v) == pytest.approx(expected)


@pytest.mark.parametrize("v, expected", [(1, "1,0×"), (0.5, "0,5×"), (1.3, "1,3×"), (2, "2,0×")])
def test_TTS6_format_rate(core, v, expected):
    assert core("formatRate", v) == expected


# ---------- TTS-8 : minuterie ----------
@pytest.mark.parametrize("cur, chapters, expected", [
    (None, True, 15), (15, True, 30), (30, True, 60), (60, True, "chapter"), ("chapter", True, None),
    (60, False, None),   # PDF : pas d'option « fin du chapitre »
])
def test_TTS8_next_sleep_option(core, cur, chapters, expected):
    assert core("nextSleepOption", cur, chapters) == expected


@pytest.mark.parametrize("left, expected", [
    (None, "⏲"), ("chapter", "Fin chap."), (15 * 60_000, "15 min"), (14 * 60_000 + 1, "15 min"),
    (59_000, "1 min"), (0, "0 min"),
])
def test_TTS8_format_sleep(core, left, expected):
    assert core("formatSleep", left) == expected
