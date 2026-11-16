#!/bin/bash
# Stratégie de test de la Liseuse
#   ./test.sh impact    -> tests liés aux fichiers modifiés depuis la dernière publication
#                          + socle stratégique, sur les 3 cibles (à chaque changement)
#   ./test.sh rapide    -> unitaires + socle stratégique sur iPhone (~30 s, pendant le développement)
#   ./test.sh livraison -> unitaires + TOUT sur iPhone + socle stratégique sur iPad et Chromium
#   ./test.sh complet   -> tout, partout (gros changement, montée de version des bibliothèques)
#   ./test.sh -k PROG   -> passe les options telles quelles à pytest (3 cibles)
set -e
cd "$(dirname "$0")"
if [ ! -x .venv/bin/pytest ]; then
  echo "Installation des outils de test (une seule fois)…"
  python3 -m venv .venv
  .venv/bin/pip install -q -r requirements-dev.txt
  .venv/bin/python -m playwright install webkit chromium
fi
PY=".venv/bin/pytest -p no:cacheprovider -n auto"
case "$1" in
  rapide)
    $PY tests/test_core.py
    $PY --target webkit-iphone -m strategic ;;
  impact)
    K=$(.venv/bin/python tests/impact.py)
    if [ "$K" = "*" ]; then
      echo "→ changement transversal (app.js, tests…) : mode livraison"; exec "$0" livraison
    elif [ -z "$K" ]; then
      echo "→ aucun fichier de l'app modifié : socle stratégique seulement"; $PY -m strategic
    else
      echo "→ tests ciblés : $K (+ socle stratégique)"; $PY -k "$K" ; $PY -m strategic -k "not ($K)"
    fi ;;
  livraison)
    $PY tests/test_core.py
    $PY --target webkit-iphone
    $PY --target webkit-ipad --target chromium-iphone -m strategic ;;
  complet)
    $PY ;;
  *)
    $PY "$@" ;;
esac
