"""Fabrique les livres de test (déterministes) dans tests/fixtures/build/.

Chaque fichier cible des exigences précises de SPEC.md :
- sample.pdf      : 5 pages A4 (PDF-1, PROG-*)
- long.pdf        : 30 pages (PDF-2 : virtualisation des pages)
- corrupt.pdf     : extension .pdf mais contenu invalide (PDF-3)
- sample.epub     : 3 chapitres + cas limites (EPUB-1..5, BIB-4)
- broken.epub     : zip sans container.xml (EPUB-6)
- notes.txt       : fichier refusé (BIB-3)
- NoTitle.EPUB    : EPUB sans dc:title, extension en majuscules (BIB-3, BIB-4)
"""
import os
import struct
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(HERE, "build")

LOREM = ("Il était une fois un texte assez long pour tester le défilement automatique "
         "de la liseuse, avec des phrases qui se suivent tranquillement. ")


def tiny_png(w=40, h=30, color=(30, 120, 200)):
    raw = b"".join(b"\x00" + bytes(color) * w for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def make_pdf(path, n_pages):
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", None,
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for p in range(n_pages):
        lines = [f"BT /F1 22 Tf 60 780 Td (Page {p + 1}) Tj ET"]
        lines += [f"BT /F1 12 Tf 60 {740 - i * 22} Td (Ligne {i + 1} de la page {p + 1}.) Tj ET"
                  for i in range(30)]
        stream = "\n".join(lines)
        objs.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        cid = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents {cid} 0 R "
                    f"/Resources << /Font << /F1 3 0 R >> >> >>")
        kids.append(f"{len(objs)} 0 R")
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as f:
        f.write(out)


def xhtml(title, body):
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">'
            f'<head><title>{title}</title><link rel="stylesheet" href="../Styles/evil.css"/>'
            '<script>window.__pwned = true;</script></head>'
            f'<body>{body}</body></html>')


def make_epub(path, title="Mon livre de test", with_container=True):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        if with_container:
            z.writestr("META-INF/container.xml",
                       '<?xml version="1.0"?><container version="1.0" '
                       'xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>'
                       '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
                       "</rootfiles></container>")
        paras = lambda c: "".join(f"<p>Chapitre {c}, paragraphe {i}. {LOREM * 2}</p>" for i in range(1, 31))
        ch1 = ("<h1 id=\"debut\">Chapitre 1</h1>"
               '<p id="liens"><a id="lien-fin" href="ch3.xhtml#fin">Aller à la fin</a> · '
               '<a id="lien-note" href="#note1">note</a> · '
               '<a id="lien-ext" href="https://example.com/">site</a></p>'
               '<img id="photo" src="../Images/ma%20photo.png" alt="photo"/>'
               '<p id="piege" onclick="window.__pwned=true" style="color:red">Paragraphe piégé.</p>'
               '<style>body{display:none}</style><script>window.__pwned = true;</script>'
               + paras(1) + '<p id="note1">Note 1.</p>')
        ch2 = '<h1>Chapitre 2</h1><svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ' \
              'viewBox="0 0 40 30" width="100%"><image id="svgimg" width="40" height="30" ' \
              'xlink:href="../Images/ma%20photo.png"/></svg>' + paras(2)
        ch3 = ("<h1>Chapitre 3</h1>" + paras(3)
               + '<p id="special">L’été  dernier, une <em>baleine</em> Élégante passa.</p>'
               + '<p id="fin">Fin du livre.</p>')
        for name, body in (("ch1", ch1), ("ch2", ch2), ("ch3", ch3)):
            z.writestr(f"OEBPS/Text/{name}.xhtml", xhtml(name, body))
        z.writestr("OEBPS/Styles/evil.css", "body { display: none !important; }")
        z.writestr("OEBPS/Images/ma photo.png", tiny_png())
        meta = f"<dc:title>{title}</dc:title>" if title else ""
        # Manifeste volontairement dans le désordre : seul l'ordre de la spine compte (EPUB-1)
        z.writestr("OEBPS/content.opf",
                   '<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" '
                   'unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
                   f'<dc:identifier id="id">test</dc:identifier>{meta}<dc:language>fr</dc:language></metadata>'
                   "<manifest>"
                   '<item id="c3" href="Text/ch3.xhtml" media-type="application/xhtml+xml"/>'
                   '<item id="c1" href="Text/ch1.xhtml" media-type="application/xhtml+xml"/>'
                   '<item id="c2" href="Text/ch2.xhtml" media-type="application/xhtml+xml"/>'
                   '<item id="img" href="Images/ma%20photo.png" media-type="image/png"/>'
                   '<item id="css" href="Styles/evil.css" media-type="text/css"/>'
                   "</manifest>"
                   '<spine><itemref idref="c1"/><itemref idref="c2"/><itemref idref="c3"/></spine></package>')


def make_pdf_without_text(path):
    """Une page « scannée » : uniquement un dessin, aucun texte (SRCH-6)."""
    stream = "0 0 1 rg 100 100 300 400 re f"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [4 0 R] /Count 1 >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 3 0 R >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer << /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    with open(path, "wb") as f:
        f.write(out)


def build():
    os.makedirs(BUILD, exist_ok=True)
    make_pdf(os.path.join(BUILD, "sample.pdf"), 5)
    make_pdf(os.path.join(BUILD, "long.pdf"), 30)
    make_pdf_without_text(os.path.join(BUILD, "scan.pdf"))
    with open(os.path.join(BUILD, "corrupt.pdf"), "wb") as f:
        f.write(b"%PDF-1.4\nceci n'est pas un vrai PDF\n")
    make_epub(os.path.join(BUILD, "sample.epub"))
    make_epub(os.path.join(BUILD, "broken.epub"), with_container=False)
    make_epub(os.path.join(BUILD, "NoTitle.EPUB"), title=None)
    with open(os.path.join(BUILD, "notes.txt"), "w") as f:
        f.write("pas un livre")
    return BUILD


if __name__ == "__main__":
    print(build())
