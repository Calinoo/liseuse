"""Choisit les tests à lancer selon les fichiers modifiés (analyse d'impact).

Compare l'arbre de travail à la dernière version publiée (origin/main) et
affiche une expression pytest « -k ». Utilisé par ./test.sh impact.
"""
import subprocess
import sys

# fichier modifié -> familles d'exigences concernées (préfixes des noms de tests)
IMPACT = {
    "core.js": ["test_core"],
    "style.css": ["AFF", "NAV", "SRCH1", "DEF10", "DEF6"],
    "index.html": ["AFF", "NAV", "SRCH", "BIB1", "BIB2", "DEF1", "DEF3", "OFF3"],
    "sw.js": ["OFF"],
    "manifest.webmanifest": ["OFF3"],
    "icons/": ["OFF"],
    "vendor/pdf": ["PDF", "SRCH", "PROG4"],
    "vendor/jszip": ["EPUB", "BIB4"],
    "tests/fixtures/": ["*"],
    "tests/conftest.py": ["*"],
    "tests/helpers.py": ["*"],
    "app.js": ["*"],          # app.js touche à tout : suite complète
}


def changed_files(base):
    out = subprocess.run(["git", "diff", "--name-only", base], capture_output=True, text=True).stdout
    untracked = subprocess.run(["git", "ls-files", "--others", "--exclude-standard"],
                               capture_output=True, text=True).stdout
    return sorted(set((out + untracked).split()))


def expression(files):
    fams = set()
    for f in files:
        if f.startswith("tests/test_"):
            fams.add(f.split("/")[-1].removesuffix(".py"))
            continue
        for prefix, targets in IMPACT.items():
            if f.startswith(prefix):
                fams.update(targets)
    if "*" in fams:
        return "*"
    return " or ".join(sorted(fams)) if fams else ""


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "origin/main"
    files = changed_files(base)
    print(expression(files))
    print("fichiers modifiés : " + (", ".join(files) or "aucun"), file=sys.stderr)
