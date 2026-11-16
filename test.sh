#!/bin/bash
# Lance toute la suite de régression (unitaires + bout en bout sur 3 cibles).
# Usage : ./test.sh                      -> tout
#         ./test.sh --target webkit-iphone -> une seule cible (rapide)
#         ./test.sh -k PROG               -> seulement les exigences PROG-*
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/pytest ]; then
  echo "Installation des outils de test (une seule fois)…"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
  .venv/bin/python -m playwright install webkit chromium
fi
exec .venv/bin/pytest -p no:cacheprovider "$@"
